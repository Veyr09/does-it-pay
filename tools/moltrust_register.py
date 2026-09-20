"""Register a keyless did:moltrust identity and read back its trust score.

The registration challenge expires in a few minutes, so the proof-of-work is solved and
the POST sent inside one run rather than across separate steps. Key material is written to
secrets/ and never printed.
"""
import base64
import binascii
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

API = 'https://api.moltrust.ch'
H = {'Content-Type': 'application/json', 'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYFILE = os.path.join(ROOT, 'secrets', 'moltrust.json')


def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url, payload, timeout=60):
    req = urllib.request.Request(url, headers=H, data=json.dumps(payload).encode())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'raw': body[:800]}


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
    """Find a nonce whose sha256(seed + nonce) has >= difficulty leading zero bits."""
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


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ch = get(f'{API}/identity/register-challenge')
    challenge = ch['challenge']
    pow_spec = ch['pow']
    print(f"challenge fetched, pow difficulty {pow_spec['difficulty_bits']} bits, "
          f"expires in {max(0, ch['expires_at'] - int(time.time()))}s", flush=True)

    nonce, tried, secs = solve_pow(pow_spec['seed'], pow_spec['difficulty_bits'])
    if nonce is None:
        print(f'proof-of-work not solved in budget after {tried:,} attempts')
        return 1
    digest = hashlib.sha256((pow_spec['seed'] + nonce).encode()).hexdigest()
    print(f'pow solved in {secs:.2f}s after {tried:,} attempts: nonce={nonce} '
          f'sha256={digest[:16]}… ({leading_zero_bits(bytes.fromhex(digest))} leading zero bits)',
          flush=True)

    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw,
                                        serialization.PublicFormat.Raw)
    sig = key.sign(challenge.encode())

    # public_key must be >= 64 chars, so it is hex. The signature encoding is not stated,
    # and the message being signed may be the challenge or one of its dotted parts, so the
    # combinations are tried against one fresh challenge rather than guessed.
    pub_hex = binascii.hexlify(pub).decode()
    parts = challenge.split('.')
    messages = [('challenge', challenge)]
    if len(parts) == 3:
        messages.append(('third-part', parts[2]))
        messages.append(('seed.ts', '.'.join(parts[:2])))
    encodings = []
    for mname, msg in messages:
        s_raw = key.sign(msg.encode())
        encodings += [
            (f'{mname}/sig-hex', pub_hex, binascii.hexlify(s_raw).decode()),
            (f'{mname}/sig-b64', pub_hex, base64.b64encode(s_raw).decode()),
            (f'{mname}/sig-b64url', pub_hex,
             base64.urlsafe_b64encode(s_raw).decode().rstrip('=')),
        ]
    result = None
    for name, pub_s, sig_s in encodings:
        status, body = post(f'{API}/identity/register-pop', {
            'public_key': pub_s, 'challenge': challenge, 'signature': sig_s,
            'pow_nonce': nonce, 'display_name': 'does-it-pay',
            'platform': 'taskmarket'})
        print(f'  register-pop [{name}] -> HTTP {status} {json.dumps(body)[:220]}', flush=True)
        if status < 300:
            result = body
            break
    if not result:
        return 1

    os.makedirs(os.path.dirname(KEYFILE), exist_ok=True)
    with open(KEYFILE, 'w', encoding='utf-8') as f:
        json.dump({'did': result.get('did'),
                   'private_key_hex': binascii.hexlify(key.private_bytes(
                       serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                       serialization.NoEncryption())).decode(),
                   'public_key_hex': binascii.hexlify(pub).decode(),
                   'registered_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   'registration_response': result}, f, indent=1)
    print(f"\nDID: {result.get('did')}", flush=True)

    did = result.get('did')
    score = get(f'{API}/skill/trust-score/{urllib.parse.quote(did)}')
    out = os.path.join(ROOT, 'data', 'moltrust_trust_score.json')
    json.dump(score, open(out, 'w'), indent=1)
    print('\ntrust-score response:')
    print(json.dumps(score, indent=1))
    return 0


if __name__ == '__main__':
    import urllib.parse
    raise SystemExit(main())
