"""Capture every resource listed in Coinbase's x402 Bazaar, with its 30-day call volume.

The discovery API publishes, per listing, `quality.l30DaysTotalCalls`, `l30DaysUniquePayers`
and the price each accepted payment scheme demands. Multiplied out that is a complete revenue
distribution for the x402 economy, which nobody seems to have published. This only captures;
tools/x402_economics.py does the arithmetic.

The capture is written whole, with the reported `pagination.total` alongside it, so a short
read is detectable rather than silent - the mistake that cost this repo a wrong headline once.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources'
H = {'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'evidence', 'x402_bazaar')
PAGE = 100


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    return None


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.makedirs(OUT, exist_ok=True)
    items, offset, reported_total = {}, 0, None
    while True:
        d = get(f'{API}?limit={PAGE}&offset={offset}')
        page = d.get('items') or []
        reported_total = (d.get('pagination') or {}).get('total', reported_total)
        for it in page:
            # `resource` is the listing's identity; a repeat means the window shifted under us.
            items[it['resource']] = it
        offset += PAGE
        if offset % 1000 == 0 or not page:
            print(f'  {len(items):6d} captured / {reported_total} reported', flush=True)
        if not page or offset >= (reported_total or 0):
            break
        if offset > 100000:
            raise RuntimeError('pagination did not terminate')

    stamp = time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime())
    short = (reported_total or 0) - len(items)
    payload = {'captured_utc': stamp, 'reported_total': reported_total,
               'captured_count': len(items), 'shortfall': short,
               'items': list(items.values())}
    dest = os.path.join(OUT, 'capture.json')
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(payload, f, separators=(',', ':'))

    # The full capture is ~47 MB, almost all of it request/response examples nothing here
    # reads. The slim one carries exactly the fields tools/x402_economics.py uses, so the
    # published figures stay reproducible from a file small enough to live in the repo.
    slim = dict(payload)
    slim['items'] = [{
        'resource': it['resource'],
        'quality': {k: (it.get('quality') or {}).get(k)
                    for k in ('l30DaysTotalCalls', 'l30DaysUniquePayers', 'lastCalledAt')},
        'accepts': [{k: a.get(k) for k in ('network', 'asset', 'scheme',
                                           'maxAmountRequired', 'amount')}
                    for a in (it.get('accepts') or [])],
    } for it in payload['items']]
    slim_dest = os.path.join(OUT, 'capture_slim.json')
    with open(slim_dest, 'w', encoding='utf-8') as f:
        json.dump(slim, f, separators=(',', ':'))
    print(f'\nwrote {dest}  ({os.path.getsize(dest) / 1e6:.1f} MB, everything)')
    print(f'wrote {slim_dest}  ({os.path.getsize(slim_dest) / 1e6:.1f} MB, '
          f'the one the analysis reads)')
    print(f'  {len(items)} distinct resources against {reported_total} reported'
          + (f'  <- SHORT BY {short}, treat totals as a lower bound' if short > 0 else
             '  (complete)'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
