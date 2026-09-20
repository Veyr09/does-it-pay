"""Historical basis, built from the pinned-pool allowlist.

v1 resolved pools by symbol search, which let a memecoin called NFLX into the sample. This
version reads `data/verified_tokens.json`, where every pool is fixed by address and was
sanity-checked against spot, so the baselines the board quotes and the series the study
publishes come from the same pools.
"""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse, statistics as st
from datetime import datetime, timezone

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/140.0 Safari/537.36', 'Accept': 'application/json'}
HERE = os.path.dirname(__file__)
CACHE = os.path.join(HERE, '..', 'data', 'cache2')
os.makedirs(CACHE, exist_ok=True)
_last = [0.0]


def get(url, tries=5, timeout=45):
    for i in range(tries):
        gap = time.time() - _last[0]
        if gap < 2.5:
            time.sleep(2.5 - gap)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(20 * (i + 1)); continue
            if i == tries - 1: raise
            time.sleep(3 + 3 * i)
        except Exception:
            if i == tries - 1: raise
            time.sleep(3 + 3 * i)


def cached(name, fn, ttl=3600):
    p = os.path.join(CACHE, name + '.json')
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl:
        return json.load(open(p, encoding='utf-8'))
    d = fn()
    json.dump(d, open(p, 'w', encoding='utf-8'))
    return d


def session(ts):
    dt = datetime.fromtimestamp(ts, timezone.utc)
    if dt.weekday() >= 5:
        return 'weekend'
    m = dt.hour * 60 + dt.minute
    return 'regular' if 13 * 60 + 30 <= m < 20 * 60 else 'closed'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tokens = json.load(open(os.path.join(HERE, '..', 'data', 'verified_tokens.json'), encoding='utf-8'))
    out = []
    for t, v in tokens.items():
        pool = v['pair']
        try:
            oc = cached('oh_' + t, lambda: get(
                f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}'
                f'/ohlcv/hour?aggregate=1&limit=1000'))
            yf = cached('yf_' + t, lambda: get(
                f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}'
                f'?interval=1h&range=60d&includePrePost=true'))
        except Exception as e:
            print(f'{t}: fetch failed {type(e).__name__}', flush=True); continue
        try:
            bars = {int(ts) // 3600 * 3600: float(c)
                    for ts, o, h, l, c, vol in oc['data']['attributes']['ohlcv_list']}
            r = yf['chart']['result'][0]
            spot = {int(ts) // 3600 * 3600: float(c)
                    for ts, c in zip(r['timestamp'], r['indicators']['quote'][0]['close']) if c is not None}
        except Exception as e:
            print(f'{t}: parse failed {type(e).__name__}', flush=True); continue
        sh = sorted(spot); j, last = 0, None
        series = []
        for h in sorted(bars):
            while j < len(sh) and sh[j] <= h:
                last = spot[sh[j]]; j += 1
            if last and bars[h] > 0:
                b = (bars[h] / last - 1) * 100
                if abs(b) <= 25:
                    series.append((h, round(b, 4), 0, session(h)))
        if len(series) < 150:
            print(f'{t}: only {len(series)} usable hours, skipped', flush=True); continue
        out.append({'ticker': t, 'symbol': v['symbol'], 'pool': pool,
                    'liq_usd': v['liq_usd'], 'series': series})
        print(f'{t}: {len(series)} hours', flush=True)
    json.dump(out, open(os.path.join(HERE, '..', 'data', 'basis_study.json'), 'w'), default=str)

    print('\n=== baselines by session (mean / sd, %) ===')
    print(f"{'tkr':<6}{'hours':>7}{'regular':>18}{'weekend':>18}{'closed':>18}")
    for r in out:
        cells = []
        for s in ('regular', 'weekend', 'closed'):
            v = [b for _h, b, _x, ss in r['series'] if ss == s]
            cells.append(f"{st.mean(v):+.2f} / {st.pstdev(v):.2f}" if len(v) >= 20 else '-')
        print(f"{r['ticker']:<6}{len(r['series']):>7}{cells[0]:>18}{cells[1]:>18}{cells[2]:>18}")


if __name__ == '__main__':
    main()
