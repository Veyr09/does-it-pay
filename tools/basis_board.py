"""Produce the board's payload: live basis against each ticker's own baseline.

The baseline is the point. A raw premium against spot is a constant per ticker; what
carries information is how far today sits from that ticker's normal, split by whether the
US market is open, because the weekend distribution is a different distribution.
"""
import json, os, sys, statistics as st, urllib.request
from datetime import datetime, timezone

UA = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
SIZES_USD = (1000, 10000)

HERE = os.path.dirname(__file__)
STUDY = os.path.join(HERE, '..', 'data', 'basis_study.json')
LIVE = os.path.join(HERE, '..', 'data', 'basis_live.jsonl')
MULT = os.path.join(HERE, '..', 'data', 'multipliers.json')
OUT = os.path.join(HERE, '..', 'data', 'board.json')


def session(ts=None):
    dt = datetime.fromtimestamp(ts, timezone.utc) if ts else datetime.now(timezone.utc)
    if dt.weekday() >= 5:
        return 'weekend'
    m = dt.hour * 60 + dt.minute
    return 'regular' if 13 * 60 + 30 <= m < 20 * 60 else 'closed'


def baselines():
    """Per ticker, per session: mean and stdev of the historical basis."""
    out = {}
    if not os.path.exists(STUDY):
        return out
    for r in json.load(open(STUDY, encoding='utf-8')):
        buckets = {}
        for h, b, _v, s in r['series']:
            s = 'weekend' if s == 'weekend' else ('regular' if s == 'regular' else 'closed')
            buckets.setdefault(s, []).append(b)
        allv = [b for _h, b, _v, _s in r['series']]
        out[r['ticker']] = {
            'n': len(allv),
            'all': {'mean': st.mean(allv), 'sd': st.pstdev(allv)},
            **{k: {'mean': st.mean(v), 'sd': st.pstdev(v), 'n': len(v)}
               for k, v in buckets.items() if len(v) >= 20}}
    return out


def executable(mint, usd):
    """What a real buy of `usd` costs in price impact. A premium you cannot transact at
    is not a premium: ORCLx quotes 4.1% impact on $1,000 and 17% on $10,000."""
    url = (f'https://lite-api.jup.ag/swap/v1/quote?inputMint={USDC_MINT}&outputMint={mint}'
           f'&amount={usd * 10**6}&slippageBps=50')
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            d = json.loads(r.read().decode())
        pi = d.get('priceImpactPct')
        return round(float(pi) * 100, 3) if pi is not None else None
    except Exception:
        return None


def latest_live():
    if not os.path.exists(LIVE):
        return {}
    rows = {}
    for line in open(LIVE, encoding='utf-8'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        rows[d['ticker']] = d
    return rows


TOKENS = {}
MULTS = {}


def build():
    global TOKENS, MULTS
    MULTS = json.load(open(MULT, encoding='utf-8')) if os.path.exists(MULT) else {}
    tp = os.path.join(HERE, '..', 'data', 'verified_tokens.json')
    TOKENS = json.load(open(tp, encoding='utf-8')) if os.path.exists(tp) else {}
    base, live, sess = baselines(), latest_live(), session()
    board = []
    for t, d in sorted(live.items()):
        b = base.get(t, {})
        ref = b.get(sess) or b.get('all')
        z = None
        if ref and ref.get('sd', 0) > 1e-9:
            z = (d['basis_pct'] - ref['mean']) / ref['sd']
        # One raw token is `multiplier` shares (Token-2022 scaledUiAmountConfig), so the
        # raw quote sits above spot by exactly that. Subtract it or repeat the mistake
        # this whole project is pointing at.
        m = (MULTS.get(t) or {}).get('effective')
        implied = (m - 1) * 100 if m else None
        adjusted = round(d['basis_pct'] - implied, 4) if implied is not None else None
        board.append({
            'ticker': t, 'symbol': d['symbol'],
            'onchain': round(d['onchain']['price'], 4),
            'spot': round(d['spot']['price'], 4),
            'basis_pct': d['basis_pct'],
            'multiplier': m,
            'multiplier_premium_pct': round(implied, 4) if implied is not None else None,
            'adjusted_basis_pct': adjusted,
            'baseline_pct': round(ref['mean'], 3) if ref else None,
            'baseline_sd': round(ref['sd'], 3) if ref else None,
            'z': round(z, 2) if z is not None else None,
            'impact_pct': {str(u): executable(TOKENS.get(t, {}).get('mint'), u)
                           for u in SIZES_USD} if TOKENS.get(t) else {},
            'liquidity_usd': round(d['onchain']['liquidity_usd']),
            'vol24h_usd': round(d['onchain']['vol24h_usd']),
            'session': sess, 'ts': d['ts'],
        })
    board.sort(key=lambda r: -(abs(r['z']) if r['z'] is not None else -1))
    payload = {'generated_at': datetime.now(timezone.utc).isoformat(),
               'session': sess, 'rows': board}
    json.dump(payload, open(OUT, 'w'), indent=1)
    return payload


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    p = build()
    print(f"session={p['session']}  generated {p['generated_at']}")
    print(f"{'tkr':<6}{'raw%':>8}{'mult%':>8}{'adj%':>8}{'normal%':>9}{'z':>7}"
          f"{'imp$10k':>9}{'liq$':>13}")
    nan = float('nan')
    for r in p['rows']:
        i10 = r['impact_pct'].get('10000')
        print(f"{r['ticker']:<6}{r['basis_pct']:>8.2f}"
              f"{(r['multiplier_premium_pct'] if r['multiplier_premium_pct'] is not None else nan):>8.2f}"
              f"{(r['adjusted_basis_pct'] if r['adjusted_basis_pct'] is not None else nan):>8.2f}"
              f"{(r['baseline_pct'] if r['baseline_pct'] is not None else nan):>9.2f}"
              f"{(r['z'] if r['z'] is not None else nan):>7.2f}"
              f"{(i10 if i10 is not None else nan):>9.2f}"
              f"{r['liquidity_usd']:>13,}")
