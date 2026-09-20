"""Monthly on-chain settlement across the agent task-marketplace category (Base only).

Reads the ERC-20 transfer history of every escrow contract the platforms' own APIs name,
and counts only transfers OUT of an escrow — money actually reaching a worker — so that
deposits and refunds do not double-count.
"""
import json, os, sys, time, urllib.parse, urllib.request, collections

UA = {'User-Agent': 'Mozilla/5.0'}
HERE = os.path.dirname(__file__)

ESCROWS = {
    'Claw Earn': ['0xa2808f8bf0ebbea771b8ea9ef388d177e3a9edb8',
                  '0xd59439e366f6d27a9f162f6cabca66c4fca43fea',
                  '0x336541126a20d6738b96dce848978d12d0af383c',
                  '0x1845e2dc0929a9fbf5361aff34ca1f3dea0e27be'],
    'taskmarket.dev': ['0xddc6cc3e4d11c1f3527b867c7dad4ed9869c33f7'],
    'AgentPact': ['0x588168712bF758aFD747bF46471afa53f9599A64'],
}


def transfers(addr, pages=8):
    url = f'https://base.blockscout.com/api/v2/addresses/{addr}/token-transfers?type=ERC-20'
    items, n = [], 0
    while url and n < pages:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            print(f'  {addr[:10]} page {n} failed: {type(e).__name__}', flush=True)
            break
        items += d.get('items', [])
        np = d.get('next_page_params')
        n += 1
        if not np:
            break
        url = (f'https://base.blockscout.com/api/v2/addresses/{addr}'
               f'/token-transfers?type=ERC-20&' + urllib.parse.urlencode(np))
        time.sleep(0.5)
    return items


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    out = collections.defaultdict(lambda: collections.Counter())
    for platform, addrs in ESCROWS.items():
        for a in addrs:
            for t in transfers(a):
                if t['from']['hash'].lower() != a.lower():
                    continue          # only money leaving escrow counts as settlement
                v = int(t['total']['value']) / 10 ** int(t['total']['decimals'])
                out[platform][t['timestamp'][:7]] += v
            time.sleep(0.4)
        print(f'{platform}: {sum(out[platform].values()):,.2f} USDC out, '
              f'{len(out[platform])} months', flush=True)

    months = sorted({m for p in out.values() for m in p})
    print('\n=== USDC paid OUT of escrow, by month ===')
    print(f"{'platform':<16}" + ''.join(f'{m[2:]:>10}' for m in months) + f"{'total':>10}")
    for p in sorted(out, key=lambda k: -sum(out[k].values())):
        row = ''.join(f'{out[p].get(m, 0):>10,.0f}' for m in months)
        print(f'{p:<16}{row}{sum(out[p].values()):>10,.0f}')
    tot = [sum(out[p].get(m, 0) for p in out) for m in months]
    print(f"{'ALL':<16}" + ''.join(f'{v:>10,.0f}' for v in tot) + f'{sum(tot):>10,.0f}')
    json.dump({p: dict(c) for p, c in out.items()},
              open(os.path.join(HERE, '..', 'data', 'category_monthly.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
