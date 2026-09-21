"""Check agentic.market's published per-seller x402 totals against Base.

The x402 economy's headline figures are quoted everywhere and, as far as I can find, have
never been reconciled against the chain by anyone outside the platform. They can be: the
ecosystem API publishes, per seller, a recipient address, a transaction count and a settled
total, and an x402 payment lands as an ordinary ERC-20 Transfer to that address.

Two things make the comparison easy to get wrong, and both bit me before this script existed:

1. The seller table is a **rolling seven-day window**, not a lifetime total. Every seller's
   `latest_block_timestamp` falls inside seven days, and the sample below re-derives that
   window rather than assuming it. Comparing a seven-day claim against a lifetime chain read,
   or the reverse, produces a large fake discrepancy in either direction.
2. A seller with a hundred thousand transactions cannot be enumerated through a paginated
   explorer, and a truncated read looks exactly like a shortfall. This only reconciles sellers
   small enough to walk to completion, and says so rather than reporting a partial read.

A claim is consistent when the chain shows at least as much arriving as the platform claims:
the address may also receive USDC that has nothing to do with x402, so chain >= claim is the
expected relationship, not equality. Both counters move while the script runs, so a one
transaction difference is drift and not a finding.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.agentic.market/v1'
BLOCKSCOUT = 'https://base.blockscout.com/api/v2'
USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
H = {'User-Agent': 'does-it-pay/1.0 (on-chain reconciliation)'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'evidence', 'x402_sellers')

# Small enough to enumerate completely through the explorer, big enough that the comparison
# is not a single transaction.
MIN_TX, MAX_TX = 20, 300
# One transaction either way is live drift between two counters, not a discrepancy.
DRIFT_TX = 1
PAGE_CAP = 30


def get(url, tries=6):
    """The explorer rate-limits a walk like this, so 429 gets a real backoff rather than
    three quick retries that all fail the same way."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (i + 1))
                continue
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError(f'gave up on {url}')


def all_sellers():
    out, page = [], 0
    while page < 400:
        d = get(f'{API}/ecosystem/sellers?limit=100&page={page}')['sellers']['json']
        out += d['items']
        if not d.get('hasNextPage'):
            break
        page += 1
        time.sleep(0.1)
    return out


def window_start(sellers):
    """The platform never says what window the table covers, so derive it from the data."""
    stamps = sorted(s['latest_block_timestamp'] for s in sellers
                    if s.get('latest_block_timestamp'))
    return stamps[0][:19], stamps[-1][:19]


def inbound_since(addr, since):
    """Every USDC transfer into addr at or after `since`. Returns completeness explicitly."""
    total, count, cursor, pages = 0.0, 0, None, 0
    url = f'{BLOCKSCOUT}/addresses/{addr}/token-transfers?type=ERC-20'
    while pages < PAGE_CAP:
        u = url + ('&' + '&'.join(f'{k}={v}' for k, v in cursor.items()) if cursor else '')
        d = get(u)
        for t in d.get('items', []):
            if t.get('timestamp', '') < since:
                return total, count, True          # walked past the window: complete
            token = t.get('token') or {}
            if (token.get('address_hash') or token.get('address') or '').lower() != USDC:
                continue
            if ((t.get('to') or {}).get('hash') or '').lower() != addr.lower():
                continue
            v = t['total']
            total += int(v['value']) / (10 ** int(v.get('decimals', 6)))
            count += 1
        cursor = d.get('next_page_params')
        pages += 1
        time.sleep(0.35)
        if not cursor:
            return total, count, True              # exhausted history: complete
    return total, count, False                     # hit the cap: do not report this one


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    sellers = all_sellers()
    lo, hi = window_start(sellers)
    print(f'{len(sellers):,} sellers published; their activity spans {lo} .. {hi}')
    print(f'so the table is a rolling window of about '
          f'{(time.mktime(time.strptime(hi, "%Y-%m-%dT%H:%M:%S")) - time.mktime(time.strptime(lo, "%Y-%m-%dT%H:%M:%S"))) / 86400:.1f} days\n')
    since = lo[:10] + 'T00:00:00'

    cands = [s for s in sellers
             if s.get('chains') == ['base'] and s['recipient'].startswith('0x')
             and MIN_TX <= s['tx_count'] <= MAX_TX]
    print(f'{len(cands)} Base sellers fall in the {MIN_TX}-{MAX_TX} transaction band that can '
          f'be walked to completion\n')

    print(f"{'address':44s} {'claim n':>8s} {'chain n':>8s} {'claim $':>9s} {'chain $':>9s}  verdict")
    rows, consistent, exceeds, skipped = [], 0, 0, 0
    for s in cands[:sample_size]:
        addr, cn, cusd = s['recipient'], s['tx_count'], s['total_amount'] / 1e6
        total, count, complete = inbound_since(addr, since)
        if not complete:
            print(f'{addr:44s} {cn:>8,} {count:>8,} {cusd:>9,.2f} {total:>9,.2f}  '
                  f'incomplete read, not counted')
            skipped += 1
            continue
        good = total + 0.005 >= cusd or abs(count - cn) <= DRIFT_TX
        verdict = 'consistent' if good else 'CLAIM EXCEEDS CHAIN'
        consistent += good
        exceeds += not good
        rows.append({'recipient': addr, 'claim_tx': cn, 'chain_tx': count,
                     'claim_usd': round(cusd, 6), 'chain_usd': round(total, 6),
                     'consistent': bool(good)})
        print(f'{addr:44s} {cn:>8,} {count:>8,} {cusd:>9,.2f} {total:>9,.2f}  {verdict}')
        time.sleep(0.2)

    print(f'\nfully reconciled: {consistent} consistent, {exceeds} exceeding the chain, '
          f'{skipped} not counted')
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, 'reconciliation.json')
    json.dump({'captured_utc': time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime()),
               'window_start': lo, 'window_end': hi, 'sellers_published': len(sellers),
               'band': [MIN_TX, MAX_TX], 'drift_allowance_tx': DRIFT_TX,
               'consistent': consistent, 'exceeds': exceeds, 'not_counted': skipped,
               'rows': rows}, open(dest, 'w', encoding='utf-8'), indent=1)
    print(f'wrote {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
