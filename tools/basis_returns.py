"""Does an unusually cheap token actually pay you?

Rebuilds token price and spot price side by side from the cached raw data, then asks:
conditional on the basis z-score, what is the TOKEN's own forward USD return, against
the unconditional baseline and against a shuffled control.
"""
import json, os, statistics as st, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import basis_study as bs

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WINDOW = 168
HORIZONS = (4, 8, 24)
TICKERS = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'META', 'GLD', 'CRCL',
           'MSTR', 'COIN', 'HOOD', 'AMZN', 'GOOGL']


def build():
    out = []
    for t in TICKERS:
        pool = None
        for sym in (t + 'x', t):
            try:
                pool = bs.deepest_pool(sym)
            except Exception:
                pool = None
            if pool:
                break
        if not pool:
            continue
        liq, pid, pname = pool
        try:
            oc = bs.onchain_hourly(pid, sym)
            sp = bs.spot_hourly(t)
        except Exception:
            continue
        hours = sorted(oc)
        sp_hours = sorted(sp)
        j, last = 0, None
        rows = []
        for h in hours:
            while j < len(sp_hours) and sp_hours[j] <= h:
                last = sp[sp_hours[j]]
                j += 1
            if last and oc[h]['c'] > 0:
                rows.append({'h': h, 'tok': oc[h]['c'], 'spot': last,
                             'basis': (oc[h]['c'] / last - 1) * 100})
        if len(rows) > 300:
            out.append({'ticker': t, 'rows': rows})
            print(f'{t}: {len(rows)} hours', flush=True)
    return out


def test(data, shuffle=False):
    import random
    random.seed(11)
    res = {}
    for h in HORIZONS:
        hi, lo, base = [], [], []
        for d in data:
            rows = d['rows']
            b = [r['basis'] for r in rows]
            if shuffle:
                idx = list(range(len(rows)))
                random.shuffle(idx)
                b = [rows[i]['basis'] for i in idx]
            for i in range(WINDOW, len(rows) - h):
                w = b[i - WINDOW:i]
                m, s = st.mean(w), st.pstdev(w)
                if s < 1e-9:
                    continue
                z = (b[i] - m) / s
                ret = (rows[i + h]['tok'] / rows[i]['tok'] - 1) * 100
                base.append(ret)
                if z > 1.5:
                    hi.append(ret)
                elif z < -1.5:
                    lo.append(ret)
        res[h] = (base, hi, lo)
    return res


def show(label, res):
    print(f'\n=== {label} — forward TOKEN return, % ===')
    print(f"{'h':>4}{'bucket':>10}{'n':>7}{'mean':>9}{'baseline':>10}{'edge':>9}{'t-stat':>9}")
    for h, (base, hi, lo) in res.items():
        b = st.mean(base)
        for name, ds in (('z>+1.5', hi), ('z<-1.5', lo)):
            if len(ds) < 20:
                continue
            e = st.mean(ds) - b
            se = st.pstdev(ds) / math.sqrt(len(ds))
            print(f"{h:>4}{name:>10}{len(ds):>7}{st.mean(ds):>9.3f}{b:>10.3f}{e:>9.3f}{e/se:>9.2f}")


if __name__ == '__main__':
    data = build()
    show('real series', test(data, shuffle=False))
    show('shuffled control', test(data, shuffle=True))
