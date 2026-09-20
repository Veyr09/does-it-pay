"""Read each xStock's Token-2022 scaled-UI multiplier straight from its mint.

The premium every Solana screener prints for these tokens is, mechanically, this number:
one raw token represents `multiplier` shares, so the raw-token price sits above the share
price by exactly (multiplier - 1). A venue that does not apply the multiplier reports both
the price and the "premium" wrongly.
"""
import json, os, sys, time, urllib.request

RPC = 'https://api.mainnet-beta.solana.com'
H = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
HERE = os.path.dirname(__file__)


def rpc(method, params, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(RPC, data=json.dumps(
                {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(), headers=H)
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode())
            if 'error' in d:
                raise RuntimeError(d['error'])
            return d.get('result')
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 + 2 * i)


def multiplier(mint):
    r = rpc('getAccountInfo', [mint, {'encoding': 'jsonParsed'}])
    v = (r or {}).get('value')
    if not v:
        return None
    data = v.get('data')
    if not isinstance(data, dict):
        return None
    for e in (data.get('parsed', {}).get('info', {}).get('extensions') or []):
        if e.get('extension') == 'scaledUiAmountConfig':
            st = e.get('state') or {}
            cur = float(st.get('multiplier'))
            new = st.get('newMultiplier')
            eff = st.get('newMultiplierEffectiveTimestamp')
            effective = cur
            if new is not None and eff is not None and time.time() >= float(eff):
                effective = float(new)
            return {'multiplier': cur, 'new': float(new) if new is not None else None,
                    'effective_ts': eff, 'effective': effective}
    return None


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    toks = json.load(open(os.path.join(HERE, '..', 'data', 'xstocks_tokens.json'), encoding='utf-8'))
    want = set(json.load(open(os.path.join(HERE, '..', 'data', 'verified_tokens.json'), encoding='utf-8')))
    out = {}
    for sym, v in toks.items():
        base = sym[:-1] if sym.endswith('x') else sym
        if base not in want:
            continue
        try:
            m = multiplier(v['mint'])
        except Exception as e:
            print(f'{sym:<9} rpc error {type(e).__name__}', flush=True); continue
        if not m:
            print(f'{sym:<9} no scaledUiAmountConfig', flush=True); continue
        out[base] = m
        print(f"{sym:<9} multiplier {m['multiplier']:.9f}  effective {m['effective']:.9f}  "
              f"=> implied premium {(m['effective'] - 1) * 100:+.3f}%", flush=True)
        time.sleep(0.4)
    json.dump(out, open(os.path.join(HERE, '..', 'data', 'multipliers.json'), 'w'), indent=1)
