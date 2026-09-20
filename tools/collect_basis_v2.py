"""Sample the tokenised-equity basis from a verified allowlist.

v1 searched DexScreener by symbol and matched memecoins called NFLX and MA. This version
reads `data/verified_tokens.json` — pools pinned by address, each sanity-checked against
spot — so the weekend series is clean enough to publish.
"""
import json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/140.0 Safari/537.36'}
HERE = os.path.dirname(__file__)
TOKENS = os.path.join(HERE, '..', 'data', 'verified_tokens.json')
OUT = os.path.join(HERE, '..', 'data', 'basis_live.jsonl')
MAX_SANE_BASIS_PCT = 25.0


def fetch(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def pair_price(pair_addr):
    d = fetch('https://api.dexscreener.com/latest/dex/pairs/solana/' + pair_addr)
    pairs = d.get('pairs') or ([d['pair']] if d.get('pair') else [])
    if not pairs:
        return None
    p = pairs[0]
    return {'price': float(p['priceUsd']),
            'liquidity_usd': float((p.get('liquidity') or {}).get('usd') or 0),
            'vol24h_usd': float((p.get('volume') or {}).get('h24') or 0),
            'txns24h': ((p.get('txns') or {}).get('h24') or {})}


def spot(ticker):
    for host in ('query1', 'query2'):
        try:
            d = fetch(f'https://{host}.finance.yahoo.com/v8/finance/chart/'
                      f'{urllib.parse.quote(ticker)}?interval=1d&range=5d')
            m = d['chart']['result'][0]['meta']
            return {'price': m.get('regularMarketPrice'),
                    'prev_close': m.get('previousClose') or m.get('chartPreviousClose'),
                    'time': m.get('regularMarketTime')}
        except Exception:
            continue
    return None


def sweep(tokens):
    ts = datetime.now(timezone.utc).isoformat()
    n = 0
    with open(OUT, 'a', encoding='utf-8') as f:
        for t, v in tokens.items():
            try:
                oc = pair_price(v['pair'])
                s = spot(t)
            except Exception:
                continue
            if not oc or not s or not s.get('price') or oc['price'] <= 0:
                continue
            basis = (oc['price'] / s['price'] - 1) * 100
            if abs(basis) > MAX_SANE_BASIS_PCT:
                continue      # pool broke or the ticker split; do not poison the series
            f.write(json.dumps({'ts': ts, 'ticker': t, 'symbol': v['symbol'],
                                'pair': v['pair'], 'onchain': oc, 'spot': s,
                                'basis_pct': round(basis, 4)}) + '\n')
            n += 1
            time.sleep(0.35)
    return n


if __name__ == '__main__':
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    tokens = json.load(open(TOKENS, encoding='utf-8'))
    print(f'{len(tokens)} verified tickers', flush=True)
    while True:
        try:
            print(f'{datetime.now(timezone.utc).isoformat()} sweep rows={sweep(tokens)}', flush=True)
        except Exception as e:
            print(f'sweep error {type(e).__name__}: {e}', flush=True)
        time.sleep(interval)
