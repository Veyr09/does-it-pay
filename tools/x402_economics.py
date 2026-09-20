"""Recompute what an x402 listing earns, from the frozen Bazaar and facilitator captures.

Two independent sources, deliberately. The CDP Bazaar publishes every listing with its 30-day
call count and its price, which gives the distribution across suppliers. agentic.market
publishes a daily ecosystem series, which gives the total the directory is a share of. Neither
is checkable against the other without both.

    python tools/x402_economics.py           # print the table
    python tools/x402_economics.py --check   # assert every published figure, non-zero on drift
"""
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAZAAR = os.path.join(ROOT, 'data', 'evidence', 'x402_bazaar', 'capture_slim.json')
AGENTIC = os.path.join(ROOT, 'data', 'evidence', 'x402_agentic', 'ecosystem_stats_30d.json')

# Testnet chains price in worthless tokens; counting them would inflate every total.
TESTNETS = {'eip155:84532', 'eip155:11155111', 'eip155:421614', 'eip155:80002'}
# Six-decimal dollar stablecoins, by contract, on the chains the directory actually uses.
# Matching on symbol is how this repo once counted a spam token called USDC with a Latin s.
STABLE_6DP = {
    '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',            # USDC, Base
    'epjfwdd5aufqssqem2qn1xzybapc8g4weggkzwytdt1v',          # USDC, Solana
    '0x3c499c542cef5e3811e1192ce70d8cc03d5c3359',            # USDC, Polygon
    '0xaf88d065e77c8cc2239327c5edb3a432268e5831',            # USDC, Arbitrum
    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',            # USDC, Ethereum
    '0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca',            # USDbC, Base
}
# Above this, the listed amount is a purchase ceiling rather than a per-call fee: the top row
# by "revenue" is a Bitrefill invoice endpoint at $1,000 a call, which is what a caller may
# spend, not what the listing charges. Calls times price is only meaningful below it.
PER_CALL_FEE_CAP_USD = 1.0
# The day the facilitator's transaction count fell by an order of magnitude and stayed down.
BREAK_DAY = '2026-09-08'

PUBLISHED = {
    'listings_reported': 14948,
    'listings_captured': 14939,
    'listings_priced': 14799,
    'calls_30d': 1005757,
    'calls_median': 2,
    'calls_top10_share_pct': 79.6,
    'listings_at_most_2_calls': 9492,
    'listings_at_most_2_calls_pct': 64.1,
    'payers_median': 1,
    'listings_one_payer': 10260,
    'api_listings': 14525,
    'api_revenue_30d': 10733.02,
    'api_revenue_median': 0.018,
    'api_under_1_dollar_pct': 95.8,
    'api_top1_share_pct': 26.4,
    'api_top10_share_pct': 58.4,
    'api_top100_share_pct': 80.3,
    'facilitator_txns_30d': 23002016,
    'facilitator_usd_30d': 982253.10,
    'facilitator_usd_per_txn': 0.0427,
    'pre_break_txns_per_day': 1289323,
    'post_break_txns_per_day': 75307,
    'txns_per_day_fall_pct': 94.2,
    'usd_per_day_fall_pct': 42.1,
    'price_per_txn_rise_x': 9.9,
}


def as_int(v):
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None


def listing_rows(capture):
    """One row per listing: its cheapest real-money price, its calls and its payers."""
    rows = []
    for item in capture['items']:
        quality = item.get('quality') or {}
        calls = quality.get('l30DaysTotalCalls')
        if calls is None:
            continue
        best = None
        for accept in item.get('accepts') or []:
            if (accept.get('network') or '') in TESTNETS:
                continue
            if (accept.get('asset') or '').lower() not in STABLE_6DP:
                continue
            units = as_int(accept.get('maxAmountRequired') or accept.get('amount'))
            if units is None:
                continue
            price = units / 1e6
            if best is None or price < best[0]:
                best = (price, accept.get('scheme'))
        if best is None:
            continue
        rows.append({'resource': item['resource'], 'calls': calls, 'price': best[0],
                     'scheme': best[1], 'payers': quality.get('l30DaysUniquePayers') or 0,
                     'revenue': calls * best[0]})
    return rows


def compute():
    bazaar = json.load(open(BAZAAR, encoding='utf-8'))
    series = json.load(open(AGENTIC, encoding='utf-8'))['stats']['json']
    rows = listing_rows(bazaar)

    calls = sorted(r['calls'] for r in rows)
    calls_desc = sorted(calls, reverse=True)
    total_calls = sum(calls)
    payers = sorted(r['payers'] for r in rows)

    api = [r for r in rows
           if r['scheme'] == 'exact' and r['price'] <= PER_CALL_FEE_CAP_USD]
    api_rev = sorted((r['revenue'] for r in api), reverse=True)
    api_total = sum(api_rev)

    txns = sum(d['total_transactions'] for d in series)
    usd = sum(d['total_amount'] for d in series) / 1e6
    pre = [d for d in series if d['bucket_start'][:10] < BREAK_DAY]
    post = [d for d in series if BREAK_DAY < d['bucket_start'][:10] <= '2026-09-19']
    pre_t = sum(d['total_transactions'] for d in pre) / len(pre)
    post_t = sum(d['total_transactions'] for d in post) / len(post)
    pre_u = sum(d['total_amount'] for d in pre) / len(pre) / 1e6
    post_u = sum(d['total_amount'] for d in post) / len(post) / 1e6

    return {
        'captured_utc': bazaar['captured_utc'],
        'listings_reported': bazaar['reported_total'],
        'listings_captured': bazaar['captured_count'],
        'listings_priced': len(rows),
        'calls_30d': total_calls,
        'calls_median': int(statistics.median(calls)),
        'calls_top10_share_pct': round(100 * sum(calls_desc[:10]) / total_calls, 1),
        'listings_at_most_2_calls': sum(1 for c in calls if c <= 2),
        'listings_at_most_2_calls_pct': round(100 * sum(1 for c in calls if c <= 2)
                                              / len(calls), 1),
        'payers_median': int(statistics.median(payers)),
        'listings_one_payer': sum(1 for p in payers if p == 1),
        'api_listings': len(api),
        'api_revenue_30d': round(api_total, 2),
        'api_revenue_median': round(statistics.median(api_rev), 3),
        'api_under_1_dollar_pct': round(100 * sum(1 for r in api_rev if r < 1)
                                        / len(api_rev), 1),
        'api_top1_share_pct': round(100 * api_rev[0] / api_total, 1),
        'api_top10_share_pct': round(100 * sum(api_rev[:10]) / api_total, 1),
        'api_top100_share_pct': round(100 * sum(api_rev[:100]) / api_total, 1),
        'facilitator_txns_30d': txns,
        'facilitator_usd_30d': round(usd, 2),
        'facilitator_usd_per_txn': round(usd / txns, 4),
        'pre_break_txns_per_day': round(pre_t),
        'post_break_txns_per_day': round(post_t),
        'txns_per_day_fall_pct': round(100 * (1 - post_t / pre_t), 1),
        'usd_per_day_fall_pct': round(100 * (1 - post_u / pre_u), 1),
        'price_per_txn_rise_x': round((post_u / post_t) / (pre_u / pre_t), 1),
        'directory_share_of_txns_pct': round(100 * total_calls / txns, 1),
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    r = compute()
    print(f"x402 Bazaar, captured {r['captured_utc']}\n")
    print(f"  listings reported / captured / priceable    {r['listings_reported']} / "
          f"{r['listings_captured']} / {r['listings_priced']}")
    print(f"  calls in the last 30 days                   {r['calls_30d']:,}")
    print(f"  median listing                              {r['calls_median']} calls, "
          f"{r['payers_median']} unique payer")
    print(f"  listings with 2 calls or fewer              "
          f"{r['listings_at_most_2_calls']:,} ({r['listings_at_most_2_calls_pct']}%)")
    print(f"  listings with exactly one unique payer      {r['listings_one_payer']:,}")
    print(f"  top 10 listings' share of all calls         {r['calls_top10_share_pct']}%\n")
    print(f"  per-call API listings (exact, <= ${PER_CALL_FEE_CAP_USD:.0f})        "
          f"{r['api_listings']:,}")
    print(f"  their implied 30-day revenue, all together  ${r['api_revenue_30d']:,.2f}")
    print(f"  median listing's 30-day revenue             ${r['api_revenue_median']:.3f}")
    print(f"  share earning under $1 in 30 days           {r['api_under_1_dollar_pct']}%")
    print(f"  top 1 / 10 / 100 share of that revenue      {r['api_top1_share_pct']}% / "
          f"{r['api_top10_share_pct']}% / {r['api_top100_share_pct']}%\n")
    print(f"  facilitator total, same 30 days             "
          f"{r['facilitator_txns_30d']:,} transactions, ${r['facilitator_usd_30d']:,.2f}")
    print(f"  average value of one transaction            ${r['facilitator_usd_per_txn']:.4f}")
    print(f"  the directory's calls as a share of those   "
          f"{r['directory_share_of_txns_pct']}%\n")
    print(f"  transactions per day, before {BREAK_DAY}      {r['pre_break_txns_per_day']:,}")
    print(f"  transactions per day, after                 {r['post_break_txns_per_day']:,}")
    print(f"  fall in transactions per day                {r['txns_per_day_fall_pct']}%")
    print(f"  fall in dollars per day                     {r['usd_per_day_fall_pct']}%")
    print(f"  rise in price per transaction               {r['price_per_txn_rise_x']}x")

    if '--check' in sys.argv:
        bad = [f'  {k}: published {v}, recomputed {r[k]}'
               for k, v in PUBLISHED.items()
               if (abs(r[k] - v) > 1e-9 if isinstance(v, float) else r[k] != v)]
        if bad:
            print('\nMISMATCH between published figures and the evidence:')
            print('\n'.join(bad))
            return 1
        print(f'\nall {len(PUBLISHED)} published figures match the evidence')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
