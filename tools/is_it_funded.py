"""Answer one question before you do the work: can this thing actually pay you?

    python tools/is_it_funded.py 0xcef19483e5fb8385d7a785c071f640a290cd1143
    python tools/is_it_funded.py --market bountybook
    python tools/is_it_funded.py --market taskmarket

Given an address, it prints what that address holds on Base and what has actually left it
in USDC. Given a market, it reads the open queue and checks every poster behind it.

No dependencies, no API key. Two public endpoints: a Base RPC and Blockscout.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

RPC = 'https://mainnet.base.org'
SCOUT = 'https://base.blockscout.com/api/v2'
USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
H = {'Content-Type': 'application/json', 'User-Agent': 'is-it-funded/1.0'}


def get(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def rpc(method, params):
    req = urllib.request.Request(RPC, headers=H, data=json.dumps(
        {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode())
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode()).get('result')


def balances(address):
    data = '0x70a08231' + address.lower().replace('0x', '').rjust(64, '0')
    usdc = rpc('eth_call', [{'to': USDC, 'data': data}, 'latest'])
    eth = rpc('eth_getBalance', [address, 'latest'])
    return (int(usdc, 16) / 1e6 if usdc and usdc != '0x' else 0.0,
            int(eth, 16) / 1e18 if eth else 0.0)


def flows(address, max_pages=40):
    """USDC in and out, and the monthly outflow. Two traps live here, so both are handled:
    spam ERC-20s must be filtered out by token address, and the transfer history must be
    paginated to the end. Getting either wrong changed my own numbers by 3x and 5x."""
    url = f'{SCOUT}/addresses/{address}/token-transfers?type=ERC-20'
    tin = tout = 0.0
    months, ignored, pages = Counter(), Counter(), 0
    while url and pages < max_pages:
        try:
            d = get(url)
        except Exception as e:
            print(f'  ! transfer page {pages} failed: {type(e).__name__}', file=sys.stderr)
            break
        for t in d.get('items', []):
            tok = t.get('token') or {}
            if (tok.get('address_hash') or tok.get('address') or '').lower() != USDC:
                ignored[tok.get('symbol') or '?'] += 1
                continue
            v = int(t['total']['value']) / 10 ** int(t['total']['decimals'])
            if t['from']['hash'].lower() == address.lower():
                tout += v
                months[t['timestamp'][:7]] += v
            if t['to']['hash'].lower() == address.lower():
                tin += v
        np = d.get('next_page_params')
        pages += 1
        if not np:
            break
        url = (f'{SCOUT}/addresses/{address}/token-transfers?type=ERC-20&'
               + urllib.parse.urlencode(np))
        time.sleep(0.4)
    return tin, tout, months, ignored, pages >= max_pages


def report(address, label=''):
    usdc, eth = balances(address)
    tin, tout, months, ignored, truncated = flows(address)
    print(f'\n{address}{"  " + label if label else ""}')
    print(f'  holds now      USDC {usdc:>12,.2f}   ETH {eth:.6f}')
    print(f'  ever received  USDC {tin:>12,.2f}')
    print(f'  ever paid out  USDC {tout:>12,.2f}')
    drift = tin - tout - usdc
    flag = '' if abs(drift) <= max(tin * 0.05, 1) else '   <-- does not reconcile, distrust'
    print(f'  in - out - held     {drift:>12,.2f}{flag}')
    if months:
        recent = sorted(months)[-6:]
        print('  paid out by month: ' + '  '.join(f'{m[2:]} ${months[m]:,.0f}' for m in recent))
    if ignored:
        print('  non-USDC transfers ignored: '
              + ', '.join(f'{n}x {s}' for s, n in ignored.most_common(4)))
    if truncated:
        print('  ! history truncated — raise --max-pages')
    return usdc


MARKETS = {
    'bountybook': ('https://api.bountybook.ai/jobs?status=open&limit=100',
                   lambda d: [(j['poster_address'], float(j.get('budget_usdc') or 0))
                              for j in d.get('jobs', []) if j.get('poster_address')]),
}


def check_market(name):
    if name == 'taskmarket':
        d = get('https://taskmarket.dev/api/tasks')
        rows = [t for t in d.get('tasks', []) if t.get('status') == 'open']
        print(f'taskmarket.dev: {len(rows)} open tasks')
        for t in rows:
            reward = float(t.get('reward') or 0) / 1e6
            print(f"  ${reward:>8.2f}  escrow tx {'yes' if t.get('escrowTxHash') else 'NO'}"
                  f"   subs={t.get('submissionCount')}   {str(t.get('referenceCode'))}")
        print('\nescrow holding the money:')
        report('0xddc6cc3e4d11c1f3527b867c7dad4ed9869c33f7', '(taskmarket escrow)')
        return
    url, extract = MARKETS[name]
    pairs = extract(get(url))
    by = Counter()
    for addr, amount in pairs:
        by[addr] += amount
    print(f'{name}: {len(pairs)} open jobs, ${sum(by.values()):,.2f} advertised, '
          f'{len(by)} distinct posters')
    for addr, advertised in by.most_common():
        held = report(addr, f'(advertised ${advertised:,.2f})')
        verdict = 'CAN PAY' if held >= advertised else (
            'CANNOT COVER ITS OWN QUEUE' if held < advertised else '')
        print(f'  verdict: {verdict}')
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('address', nargs='?', help='a Base address to check')
    ap.add_argument('--market', choices=sorted(set(MARKETS) | {'taskmarket'}),
                    help='check every poster behind a market\'s open queue')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if a.market:
        check_market(a.market)
    elif a.address:
        report(a.address)
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
