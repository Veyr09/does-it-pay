"""Daily basis over as long a window as the free data allows.

Hourly OHLCV caps at 1000 points (~42 days). Daily bars go back much further, so this
answers a question the hourly study cannot: is the per-ticker premium stable over months,
or is it drifting?
"""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse, statistics as st
from datetime import datetime, timezone

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/140.0 Safari/537.36', 'Accept': 'application/json'}
HERE = os.path.dirname(__file__)
CACHE = os.path.join(HERE, '..', 'data', 'cache_long')
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


def cached(name, fn, ttl=21600):
    p = os.path.join(CACHE, name + '.json')
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl:
        return json.load(open(p, encoding='utf-8'))
    d = fn(); json.dump(d, open(p, 'w', encoding='utf-8')); return d


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tokens = json.load(open(os.path.join(HERE, '..', 'data', 'verified_tokens.json'), encoding='utf-8'))
    rows = {}
    for t, v in tokens.items():
        try:
            oc = cached('d_' + t, lambda: get(
                f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{v['pair']}"
                f"/ohlcv/day?aggregate=1&limit=1000"))
            yf = cached('y_' + t, lambda: get(
                f'https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}'
                f'?interval=1d&range=2y'))
        except Exception as e:
            print(f'{t}: {type(e).__name__}', flush=True); continue
        try:
            bars = {datetime.fromtimestamp(int(ts), timezone.utc).strftime('%Y-%m-%d'): float(c)
                    for ts, o, h, l, c, vol in oc['data']['attributes']['ohlcv_list'] if c}
            r = yf['chart']['result'][0]
            spot = {datetime.fromtimestamp(int(ts), timezone.utc).strftime('%Y-%m-%d'): float(c)
                    for ts, c in zip(r['timestamp'], r['indicators']['quote'][0]['close']) if c}
        except Exception as e:
            print(f'{t}: parse {type(e).__name__}', flush=True); continue
        ser = {}
        for d, p in bars.items():
            s = spot.get(d)
            if s:
                b = (p / s - 1) * 100
                if abs(b) <= 25:
                    ser[d] = round(b, 4)
        if len(ser) >= 60:
            rows[t] = ser
            days = sorted(ser)
            print(f'{t}: {len(ser)} days  {days[0]} -> {days[-1]}', flush=True)
    json.dump(rows, open(os.path.join(HERE, '..', 'data', 'basis_daily.json'), 'w'))

    print('\n=== mean basis by month (%) ===')
    months = sorted({d[:7] for s in rows.values() for d in s})[-9:]
    print(f"{'tkr':<7}" + ''.join(f'{m[2:]:>9}' for m in months))
    for t, s in rows.items():
        cells = []
        for m in months:
            v = [b for d, b in s.items() if d.startswith(m)]
            cells.append(f'{st.mean(v):+.2f}' if len(v) >= 5 else '-')
        print(f'{t:<7}' + ''.join(f'{c:>9}' for c in cells))


if __name__ == '__main__':
    main()
