"""Test the dividend explanation across the whole xStocks universe.

Token universe and prices come from Jupiter's token API (authoritative mints, and its
liquidity figures are orders of magnitude saner than DexScreener's on the thin pools).
Underlying price and trailing dividends come from Yahoo. Pre-IPO and non-equity xStocks
have no public underlying and are skipped by name.
"""
import json, os, sys, time, urllib.request, urllib.parse, statistics as st, math

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/140.0 Safari/537.36', 'Accept': 'application/json'}
HERE = os.path.dirname(__file__)

# xStock symbol -> Yahoo ticker, where stripping the trailing 'x' is not enough
OVERRIDE = {'BRK.Bx': 'BRK-B', 'SKHYx': '000660.KS'}
# no public underlying, or not an equity
SKIP = {'SPCXx', 'STRCx', 'DFDVx', 'VIDAx', 'AMBRx', 'BMNRx', 'xstocks', 'Orclx',
        'STONK', '777STOCK'}


def get(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def yahoo(ticker):
    for h in ('query1', 'query2'):
        try:
            d = get(f'https://{h}.finance.yahoo.com/v8/finance/chart/'
                    f'{urllib.parse.quote(ticker)}?interval=1d&range=1y&events=div')
            r = d['chart']['result'][0]
            px = r['meta'].get('regularMarketPrice')
            ev = ((r.get('events') or {}).get('dividends') or {})
            if not px:
                return None
            return {'price': px,
                    'div_12m': sum(float(v['amount']) for v in ev.values()),
                    'yield_pct': sum(float(v['amount']) for v in ev.values()) / px * 100,
                    'payments': len(ev)}
        except Exception:
            continue
    return None


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    toks = json.load(open(os.path.join(HERE, '..', 'data', 'xstocks_tokens.json'), encoding='utf-8'))
    rows = []
    for sym, v in sorted(toks.items(), key=lambda kv: -(kv[1].get('liq') or 0)):
        if sym in SKIP or not v.get('price'):
            continue
        under = OVERRIDE.get(sym) or (sym[:-1] if sym.endswith('x') else None)
        if not under:
            continue
        y = yahoo(under)
        time.sleep(0.35)
        if not y:
            continue
        basis = (v['price'] / y['price'] - 1) * 100
        if abs(basis) > 25:
            print(f'{sym:<9} skipped, basis {basis:+.1f}% (pool broken or wrong underlying)', flush=True)
            continue
        rows.append({'symbol': sym, 'under': under, 'liq': v.get('liq') or 0,
                     'token_px': v['price'], 'spot': y['price'],
                     'yield_pct': y['yield_pct'], 'basis_pct': basis,
                     'holders': v.get('holders') or 0})
        print(f"{sym:<9}{under:<9} liq ${v.get('liq') or 0:>11,.0f}  yield {y['yield_pct']:>5.2f}%  "
              f"basis {basis:>+7.2f}%", flush=True)
    json.dump(rows, open(os.path.join(HERE, '..', 'data', 'dividend_universe.json'), 'w'), indent=1)

    def corr(a, b):
        ma, mb = st.mean(a), st.mean(b)
        n = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        d = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
        return n / d if d else 0

    print('\n=== dividend yield vs basis, by liquidity floor ===')
    print(f"{'floor $':>10}{'n':>5}{'corr':>8}{'slope':>8}{'zero-yield mean':>18}{'payer mean':>12}")
    for floor in (0, 2000, 10000, 40000, 200000):
        sub = [r for r in rows if r['liq'] >= floor]
        if len(sub) < 5:
            continue
        ys = [r['yield_pct'] for r in sub]
        bs = [r['basis_pct'] for r in sub]
        mx = st.mean(ys)
        slope = (sum((x - mx) * (y - st.mean(bs)) for x, y in zip(ys, bs))
                 / sum((x - mx) ** 2 for x in ys)) if sum((x - mx) ** 2 for x in ys) else 0
        z = [r['basis_pct'] for r in sub if r['yield_pct'] < 0.05]
        p = [r['basis_pct'] for r in sub if r['yield_pct'] >= 0.05]
        zs = f'{st.mean(z):+.3f} (n={len(z)})' if z else '-'
        ps = f'{st.mean(p):+.3f}' if p else '-'
        print(f"{floor:>10,}{len(sub):>5}{corr(ys, bs):>+8.3f}{slope:>8.3f}{zs:>18}{ps:>12}")


if __name__ == '__main__':
    main()
