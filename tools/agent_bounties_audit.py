"""Audit a GitHub-hosted bounty programme: are submissions ever merged, and were wallets paid?

Written for daydreamsai/agent-bounties, which advertises ten $1,000 first-come-first-served
bounties. The two questions a would-be contributor actually has are whether anything has ever
been accepted and whether anyone has ever been paid, and both are answerable from outside: the
first from the PR list, the second from the payout addresses contributors put in their own PR
bodies.

A wallet's current balance cannot prove what it once received, so the only hard on-chain claim
made here is about addresses with no transactions at all. That distinction is kept in the
output rather than smoothed over.

    python tools/agent_bounties_audit.py                 # re-fetch and print
    python tools/agent_bounties_audit.py --check         # assert the published figures
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

REPO = 'daydreamsai/agent-bounties'
SOLANA_RPC = 'https://api.mainnet-beta.solana.com'
USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
H = {'Content-Type': 'application/json', 'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'evidence', 'agent_bounties')
B58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
B58_RE = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
SOLANA_PUBKEY_BYTES = 32

PUBLISHED = {
    'pulls_total': 278,
    'pulls_merged': 0,
    'pulls_closed_unmerged': 37,
    'distinct_submitters': 65,
    'valid_payout_addresses': 44,
    'addresses_never_transacted': 24,
    'addresses_holding_usdc': 7,
    'largest_usdc_balance': 658.48,
}


def gh(path):
    r = subprocess.run(['gh', 'api', path], capture_output=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f'gh api {path} failed: {r.stderr.decode("utf-8", "replace")[-200:]}')
    return json.loads(r.stdout.decode('utf-8', 'replace'))


def rpc(method, params, tries=3):
    req = urllib.request.Request(SOLANA_RPC, headers=H, data=json.dumps(
        {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode())
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode()).get('result')
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def b58_decode(s):
    n = 0
    for c in s:
        if c not in B58_ALPHABET:
            return None
        n = n * 58 + B58_ALPHABET.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return b'\0' * (len(s) - len(s.lstrip('1'))) + raw


def collect():
    pulls, page = [], 1
    while page <= 10:
        batch = gh(f'repos/{REPO}/pulls?state=all&per_page=100&page={page}')
        if not batch:
            break
        pulls += batch
        page += 1
    print(f'{len(pulls)} pull requests', flush=True)

    addresses = {}
    for p in pulls:
        for match in re.findall(B58_RE, p.get('body') or ''):
            decoded = b58_decode(match)
            if decoded is not None and len(decoded) == SOLANA_PUBKEY_BYTES:
                addresses.setdefault(match, p['number'])
    print(f'{len(addresses)} valid Solana payout addresses named in PR bodies', flush=True)

    wallets = []
    for addr, pr in addresses.items():
        sigs = rpc('getSignaturesForAddress', [addr, {'limit': 1000}]) or []
        lamports = (rpc('getBalance', [addr]) or {}).get('value', 0)
        accounts = rpc('getTokenAccountsByOwner',
                       [addr, {'mint': USDC_MINT}, {'encoding': 'jsonParsed'}]) or {}
        usdc = sum(float(v['account']['data']['parsed']['info']['tokenAmount']
                         ['uiAmountString']) for v in accounts.get('value', []))
        wallets.append({'address': addr, 'pr': pr, 'transactions': len(sigs),
                        'sol': lamports / 1e9, 'usdc': usdc})
        time.sleep(0.35)

    return {
        'captured_utc': time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime()),
        'repo': REPO,
        'repo_pushed_at': gh(f'repos/{REPO}')['pushed_at'],
        'pulls': [{'number': p['number'], 'state': p['state'], 'merged_at': p['merged_at'],
                   'created_at': p['created_at'], 'user': p['user']['login']} for p in pulls],
        'wallets': wallets,
    }


def summarise(cap):
    pulls, wallets = cap['pulls'], cap['wallets']
    usdc = [w['usdc'] for w in wallets]
    return {
        'pulls_total': len(pulls),
        'pulls_merged': sum(1 for p in pulls if p['merged_at']),
        'pulls_closed_unmerged': sum(1 for p in pulls
                                     if p['state'] == 'closed' and not p['merged_at']),
        'pulls_open': sum(1 for p in pulls if p['state'] == 'open'),
        'distinct_submitters': len({p['user'] for p in pulls}),
        'first_pr': min(p['created_at'] for p in pulls)[:10],
        'latest_pr': max(p['created_at'] for p in pulls)[:10],
        'repo_pushed_at': cap['repo_pushed_at'][:10],
        'valid_payout_addresses': len(wallets),
        'addresses_never_transacted': sum(1 for w in wallets if w['transactions'] == 0),
        'addresses_holding_usdc': sum(1 for w in wallets if w['usdc'] > 0),
        'largest_usdc_balance': round(max(usdc, default=0.0), 2),
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    dest = os.path.join(OUT, 'capture.json')
    if '--check' in sys.argv and os.path.exists(dest):
        cap = json.load(open(dest, encoding='utf-8'))
    else:
        os.makedirs(OUT, exist_ok=True)
        cap = collect()
        json.dump(cap, open(dest, 'w', encoding='utf-8'), indent=1)
        print(f'wrote {dest}')

    s = summarise(cap)
    print(f"\n{cap['repo']}, captured {cap['captured_utc']}\n")
    print(f"  pull requests, all time        {s['pulls_total']}")
    print(f"  merged                         {s['pulls_merged']}")
    print(f"  closed without merge           {s['pulls_closed_unmerged']}")
    print(f"  still open                     {s['pulls_open']}")
    print(f"  distinct submitters            {s['distinct_submitters']}")
    print(f"  first / latest PR              {s['first_pr']} / {s['latest_pr']}")
    print(f"  last commit to the repository  {s['repo_pushed_at']}\n")
    print(f"  payout addresses named in PRs  {s['valid_payout_addresses']}")
    print(f"  of those, never transacted     {s['addresses_never_transacted']}  "
          f"<- these cannot have been paid at that address")
    print(f"  holding any USDC               {s['addresses_holding_usdc']}")
    print(f"  largest USDC balance seen      ${s['largest_usdc_balance']:,.2f}")
    print('\n  a balance cannot prove what an address once received, so no claim is made '
          'about\n  the addresses that have transacted')

    if '--check' in sys.argv:
        bad = [f'  {k}: published {v}, recomputed {s[k]}'
               for k, v in PUBLISHED.items()
               if (abs(s[k] - v) > 1e-9 if isinstance(v, float) else s[k] != v)]
        if bad:
            print('\nMISMATCH between published figures and the evidence:')
            print('\n'.join(bad))
            return 1
        print(f'\nall {len(PUBLISHED)} published figures match the evidence')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
