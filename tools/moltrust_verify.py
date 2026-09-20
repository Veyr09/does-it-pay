"""Bind an API key to the existing did:moltrust key, then verify DIDs and check every
anchor transaction on Base independently.

The point of the exercise is not the verify response but the anchors it names: each one
is read back from Base by transaction hash, so a mismatch between what the registry
claims and what the chain holds would show up here rather than being taken on trust.
"""
import base64
import binascii
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

API = 'https://api.moltrust.ch'
BASE_RPC = 'https://mainnet.base.org'
H = {'Content-Type': 'application/json', 'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYFILE = os.path.join(ROOT, 'secrets', 'moltrust.json')


def get(url, headers=None, timeout=30):
    h = dict(H)
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'raw': body[:600]}


def post(url, payload, headers=None, timeout=60):
    h = dict(H)
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=json.dumps(payload).encode())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'raw': body[:600]}


def leading_zero_bits(digest: bytes) -> int:
    bits = 0
    for byte in digest:
        if byte == 0:
            bits += 8
            continue
        bits += 8 - byte.bit_length()
        break
    return bits


def solve_pow(seed: str, difficulty: int, budget_s: float = 120.0):
    start = time.time()
    seed_b = seed.encode()
    n = 0
    while time.time() - start < budget_s:
        for _ in range(20000):
            nonce = f'{n:x}'
            if leading_zero_bits(hashlib.sha256(seed_b + nonce.encode()).digest()) >= difficulty:
                return nonce, n, time.time() - start
            n += 1
    return None, n, time.time() - start


def rpc(method, params):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    req = urllib.request.Request(BASE_RPC, headers=H, data=json.dumps(payload).encode())
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode()).get('result')


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    keys = json.load(open(KEYFILE, encoding='utf-8'))
    did = keys['did']
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keys['private_key_hex']))
    pub_hex = keys['public_key_hex']
    print(f'did: {did}', flush=True)

    # 1. bind an API key to the same keypair, using a fresh challenge
    api_key = keys.get('api_key')
    if not api_key:
        st, ch = get(f'{API}/identity/register-challenge')
        challenge = ch['challenge']
        pow_spec = ch['pow']
        nonce, tried, secs = solve_pow(pow_spec['seed'], pow_spec['difficulty_bits'])
        print(f'pow for signup solved in {secs:.2f}s after {tried:,} attempts', flush=True)
        sig = binascii.hexlify(key.sign(challenge.encode())).decode()
        st, body = post(f'{API}/auth/signup-did', {
            'public_key': pub_hex, 'challenge': challenge, 'signature': sig,
            'pow_nonce': nonce, 'did': did})
        print(f'signup-did -> HTTP {st} {json.dumps(body)[:400]}', flush=True)
        if st < 300:
            api_key = body.get('api_key') or body.get('apiKey') or body.get('key')
            keys['api_key'] = api_key
            keys['signup_response'] = body
            json.dump(keys, open(KEYFILE, 'w', encoding='utf-8'), indent=1)

    auth = {'X-API-Key': api_key} if api_key else {}

    # 2. verify DIDs
    targets = [did] + [a for a in sys.argv[1:]]
    out = {}
    for t in targets:
        st, body = get(f'{API}/identity/verify/{urllib.parse.quote(t)}', headers=auth)
        print(f'\nverify {t} -> HTTP {st}')
        print(json.dumps(body, indent=1)[:4000], flush=True)
        out[t] = {'status': st, 'response': body}

    # 3. independently read every anchor transaction named in the responses
    anchors = {}
    for t, rec in out.items():
        body = rec['response']
        found = []

        def walk(o, path=''):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, str) and v.startswith('0x') and len(v) == 66 \
                            and ('tx' in k.lower() or 'anchor' in k.lower() or 'hash' in k.lower()):
                        found.append((f'{path}.{k}'.lstrip('.'), v))
                    walk(v, f'{path}.{k}'.lstrip('.'))
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f'{path}[{i}]')

        walk(body)
        for where, txh in found:
            if txh in anchors:
                continue
            tx = rpc('eth_getTransactionByHash', [txh])
            rcpt = rpc('eth_getTransactionReceipt', [txh])
            anchors[txh] = {
                'referenced_at': where, 'for_did': t,
                'found_on_base': tx is not None,
                'from': (tx or {}).get('from'), 'to': (tx or {}).get('to'),
                'block': int((tx or {}).get('blockNumber', '0x0'), 16) if tx else None,
                'status': (rcpt or {}).get('status'),
                'input_len': len((tx or {}).get('input', '')),
                'input': (tx or {}).get('input', '')[:400],
            }
            print(f"\nanchor {txh} ({where}) -> on-chain={tx is not None} "
                  f"status={(rcpt or {}).get('status')} block={anchors[txh]['block']}", flush=True)

    dest = os.path.join(ROOT, 'data', 'moltrust_verify.json')
    json.dump({'verified': out, 'anchors': anchors,
               'checked_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(dest, 'w', encoding='utf-8'), indent=1)
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
