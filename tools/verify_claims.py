"""Recompute every published escrow figure from the frozen evidence in data/evidence/.

The point is that nobody has to trust the write-up. This reads the raw Blockscout
transfer pages captured at publication time, filters to USDC, and prints the same table
the post prints. If a number in the post and a number here disagree, the post is wrong.

    python tools/verify_claims.py
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
EVIDENCE = os.path.join(HERE, '..', 'data', 'evidence')
USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'

PLATFORMS = {
    'Claw Earn': ['clawescrow_a', 'clawescrow_b', 'clawescrow_c', 'clawescrow_d'],
    'taskmarket.dev': ['taskmarket_escrow'],
    'AgentPact': ['agentpact_escrow'],
}

# what the write-up claims, so a mismatch is loud rather than silent
PUBLISHED = {
    'Claw Earn': {'in': 882.25, 'out': 809.76},
    'taskmarket.dev': {'in': 2732.89, 'out': 1667.98},
    'AgentPact': {'in': 13.62, 'out': 13.62},
}
PUBLISHED_MONTHLY_TOTAL = {
    '2026-02': 2.5, '2026-03': 219, '2026-04': 316, '2026-05': 229,
    '2026-06': 430, '2026-07': 461, '2026-08': 758, '2026-09': 76,
}
TOLERANCE_PCT = 1.0


def token_address(transfer):
    t = transfer.get('token') or {}
    return (t.get('address_hash') or t.get('address') or '').lower()


def load(name):
    path = os.path.join(EVIDENCE, name + '_transfers.json')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    totals, monthly_out, spam = {}, Counter(), Counter()
    for platform, files in PLATFORMS.items():
        tin = tout = 0.0
        for name in files:
            blob = load(name)
            addr = blob['address'].lower()
            for t in blob['items']:
                if token_address(t) != USDC:
                    spam[(t.get('token') or {}).get('symbol') or '?'] += 1
                    continue
                total = t['total']
                value = int(total['value']) / 10 ** int(total['decimals'])
                if t['from']['hash'].lower() == addr:
                    tout += value
                    monthly_out[t['timestamp'][:7]] += value
                if t['to']['hash'].lower() == addr:
                    tin += value
        totals[platform] = {'in': tin, 'out': tout}

    print('USDC through each escrow, recomputed from frozen evidence')
    print(f"{'platform':<16}{'in':>12}{'out':>12}{'published in':>14}{'published out':>15}{'ok':>5}")
    all_ok = True
    for platform, v in totals.items():
        p = PUBLISHED[platform]
        ok = (abs(v['in'] - p['in']) <= p['in'] * TOLERANCE_PCT / 100
              and abs(v['out'] - p['out']) <= max(p['out'], 1) * TOLERANCE_PCT / 100)
        all_ok &= ok
        print(f"{platform:<16}{v['in']:>12,.2f}{v['out']:>12,.2f}"
              f"{p['in']:>14,.2f}{p['out']:>15,.2f}{'yes' if ok else 'NO':>5}")
    print(f"{'TOTAL':<16}{sum(v['in'] for v in totals.values()):>12,.2f}"
          f"{sum(v['out'] for v in totals.values()):>12,.2f}")

    print('\nUSDC paid OUT of escrow by month')
    print(f"{'month':<10}{'recomputed':>12}{'published':>11}{'ok':>5}")
    for month in sorted(set(monthly_out) | set(PUBLISHED_MONTHLY_TOTAL)):
        got = monthly_out.get(month, 0.0)
        said = PUBLISHED_MONTHLY_TOTAL.get(month)
        ok = said is not None and abs(got - said) <= max(said, 1) * 2 / 100
        all_ok &= ok
        print(f'{month:<10}{got:>12,.2f}{(said if said is not None else 0):>11,.0f}'
              f"{'yes' if ok else 'NO':>5}")
    print(f"{'lifetime':<10}{sum(monthly_out.values()):>12,.2f}")

    # per-worker claims about taskmarket.dev, which the post quotes directly
    blob = load('taskmarket_escrow')
    addr = blob['address'].lower()
    outs = [int(t['total']['value']) / 10 ** int(t['total']['decimals'])
            for t in blob['items']
            if token_address(t) == USDC and t['from']['hash'].lower() == addr]
    recipients = {t['to']['hash'].lower() for t in blob['items']
                  if token_address(t) == USDC and t['from']['hash'].lower() == addr}
    outs.sort()
    over_a_dollar = [v for v in outs if v >= 1]
    print('\ntaskmarket.dev, per-worker (the post quotes these)')
    for label, got, said in (
            ('outbound transfers', len(outs), 919),
            ('distinct recipients', len(recipients), 270),
            ('median payment', round(outs[len(outs) // 2], 2), 0.45),
            ('transfers >= $1', len(over_a_dollar), 366),
            ('largest single payment', round(outs[-1], 2), 100.00)):
        ok = abs(got - said) <= max(said * 0.02, 0.01)
        all_ok &= ok
        print(f'  {label:<24}{got:>12}{said:>12}{"  yes" if ok else "  NO"}')

    if spam:
        print('\nNon-USDC tokens seen in these escrows, and ignored — counting them is how '
              'the first version of this got Claw Earn wrong by 3x:')
        for sym, n in spam.most_common(8):
            print(f'  {n:>4}  {sym}')

    print('\nRESULT:', 'every published figure reproduces' if all_ok
          else 'MISMATCH — the write-up needs correcting')
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
