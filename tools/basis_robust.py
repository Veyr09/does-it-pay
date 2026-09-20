"""Three checks the first result has to survive before anything is built on it.

1. Non-overlapping samples, so autocorrelated windows stop inflating the t-stat.
2. Net of a realistic round-trip cost on a Solana DEX.
3. Against a plain price-reversal control, so the basis has to add something beyond
   'the token just dropped and bounced'.
"""
import json, os, statistics as st, sys, math, random
sys.path.insert(0, os.path.dirname(__file__))
import basis_returns as br
import basis_study as bs

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WINDOW = 168
ROUND_TRIP_COST_PCT = 0.60   # two DEX legs at ~0.25-0.30% each, before slippage


def zseries(vals):
    out = []
    for i in range(len(vals)):
        if i < WINDOW:
            out.append(None); continue
        w = vals[i - WINDOW:i]
        m, s = st.mean(w), st.pstdev(w)
        out.append((vals[i] - m) / s if s > 1e-9 else None)
    return out


def run(data, h, key, thresh, non_overlap=True):
    """key: 'basis' or 'ret24' (price-reversal control)."""
    sel, base = [], []
    for d in data:
        rows = d['rows']
        if key == 'basis':
            raw = [r['basis'] for r in rows]
        else:
            raw = [0.0] * 24 + [(rows[i]['tok'] / rows[i - 24]['tok'] - 1) * 100
                                for i in range(24, len(rows))]
        z = zseries(raw)
        step = h if non_overlap else 1
        for i in range(WINDOW, len(rows) - h, step):
            if z[i] is None:
                continue
            ret = (rows[i + h]['tok'] / rows[i]['tok'] - 1) * 100
            base.append(ret)
            if (thresh > 0 and z[i] > thresh) or (thresh < 0 and z[i] < thresh):
                sel.append(ret)
    return base, sel


def report(title, data, key):
    print(f'\n=== {title} ===')
    print(f"{'h':>4}{'bucket':>10}{'n':>6}{'mean':>9}{'base':>8}{'edge':>8}{'t':>7}{'net of cost':>12}")
    for h in (4, 8, 24):
        for thresh, name in ((-1.5, 'z<-1.5'), (1.5, 'z>+1.5')):
            base, sel = run(data, h, key, thresh)
            if len(sel) < 15:
                continue
            b, m = st.mean(base), st.mean(sel)
            e = m - b
            se = st.pstdev(sel) / math.sqrt(len(sel))
            net = (m - ROUND_TRIP_COST_PCT) if thresh < 0 else None
            netstr = f'{net:>12.3f}' if net is not None else f"{'n/a (short)':>12}"
            print(f"{h:>4}{name:>10}{len(sel):>6}{m:>9.3f}{b:>8.3f}{e:>8.3f}{e/se:>7.2f}{netstr}")


if __name__ == '__main__':
    data = br.build()
    report('basis z-score, NON-OVERLAPPING samples', data, 'basis')
    report('CONTROL: plain 24h price-reversal z-score', data, 'ret24')
    print(f"\nRound-trip cost assumed: {ROUND_TRIP_COST_PCT}% (two DEX legs, before slippage "
          f"and priority fees). A long-only trader only gets the z<-1.5 side.")
