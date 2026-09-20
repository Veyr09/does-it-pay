"""Recompute what a submission to taskmarket.dev is worth, from the frozen capture.

Every figure published in the write-up is produced here and nowhere else. Run it against
data/evidence/taskmarket_history/capture.json and data/evidence/taskmarket_escrow_transfers.json
and it prints the canonical table; --check additionally asserts the published values and exits
non-zero on any mismatch, the same contract as verify_claims.py.
"""
import collections
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURE = os.path.join(ROOT, 'data', 'evidence', 'taskmarket_history', 'capture.json')
ESCROW = os.path.join(ROOT, 'data', 'evidence', 'taskmarket_escrow_transfers.json')
ESCROW_ADDR = '0xddc6cc3e4d11c1f3527b867c7dad4ed9869c33f7'
USDC_BASE = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
PLATFORM_FEE_BPS = 750
# Anything at or below this is an action fee (accept, rate, pitch, extra submission), not a
# task funding. The smallest real reward in the capture is well above it.
FEE_CEILING_USD = 0.01

PUBLISHED = {
    'tasks': 442,
    'requesters': 58,
    'escrowed_total': 2473.49,
    'completed_tasks': 323,
    'completed_escrowed': 1484.79,
    'worker_pool': 1373.43,
    'submissions_to_completed': 18346,
    'submissions_all': 24587,
    'awards': 540,
    'ev_per_submission': 0.0749,
    'award_rate_pct': 2.94,
    'mean_submissions': 56.8,
    'median_submissions': 29,
    'max_submissions': 585,
    'stuck_tasks': 69,
    'stuck_usd': 560.66,
    'stuck_submissions': 6203,
    'never_completed_requesters': 29,
    'never_completed_usd': 603.43,
    'onchain_in': 2732.89,
    'onchain_out': 1767.98,
    'unmatched_usd': 259.38,
    'unmatched_transfers': 49,
}


def _addr(x):
    return (x.get('hash') if isinstance(x, dict) else (x or '')).lower()


def _token_addr(t):
    tk = t['token']
    if isinstance(tk, str):
        return tk.lower()
    return (tk.get('address_hash') or tk.get('address') or '').lower()


def _amount(t):
    tot = t['total']
    return int(tot['value']) / (10 ** int(tot.get('decimals', 6)))


def usd(raw):
    return int(raw or 0) / 1e6


def compute():
    cap = json.load(open(CAPTURE, encoding='utf-8'))
    tasks, rstats = cap['tasks'], cap['requester_stats']
    esc = json.load(open(ESCROW, encoding='utf-8'))

    completed = [t for t in tasks.values() if t['status'] == 'completed']
    subs_completed = [t.get('submissionCount') or 0 for t in completed]
    awards = sum((t.get('awardCount') or 0) for t in completed)
    subs_all = sum((t.get('submissionCount') or 0) for t in tasks.values())
    completed_escrowed = sum(usd(t['reward']) for t in completed)
    worker_pool = completed_escrowed * (1 - PLATFORM_FEE_BPS / 10000)

    stuck = [t for t in tasks.values() if t.get('phase') == 'awaiting_settlement']
    never = [a for a, s in rstats.items()
             if s.get('totalTasksCreated', 0) > 0 and s.get('completedCount', 0) == 0]
    by_requester_usd = collections.Counter()
    by_requester_n = collections.Counter()
    for t in tasks.values():
        by_requester_usd[t['requester'].lower()] += usd(t['reward'])
        by_requester_n[t['requester'].lower()] += 1

    transfers = [t for t in esc['items'] if _token_addr(t) == USDC_BASE]
    inbound = [t for t in transfers if _addr(t['to']) == ESCROW_ADDR]
    fundings = [t for t in inbound if _amount(t) >= FEE_CEILING_USD]
    funding_usd = sum(_amount(t) for t in fundings)
    escrowed_total = sum(usd(t['reward']) for t in tasks.values())

    return {
        'tasks': len(tasks),
        'requesters': len(rstats),
        'escrowed_total': round(escrowed_total, 2),
        'completed_tasks': len(completed),
        'completed_escrowed': round(completed_escrowed, 2),
        'worker_pool': round(worker_pool, 2),
        'submissions_to_completed': sum(subs_completed),
        'submissions_all': subs_all,
        'awards': awards,
        'ev_per_submission': round(worker_pool / sum(subs_completed), 4),
        'ev_per_submission_any': round(worker_pool / subs_all, 4),
        'award_rate_pct': round(awards / sum(subs_completed) * 100, 2),
        'mean_submissions': round(statistics.mean(subs_completed), 1),
        'median_submissions': int(statistics.median(subs_completed)),
        'max_submissions': max(subs_completed),
        'stuck_tasks': len(stuck),
        'stuck_usd': round(sum(usd(t['reward']) for t in stuck), 2),
        'stuck_submissions': sum((t.get('submissionCount') or 0) for t in stuck),
        'never_completed_requesters': len(never),
        'never_completed_tasks': sum(by_requester_n[a] for a in never),
        'never_completed_usd': round(sum(by_requester_usd[a] for a in never), 2),
        'onchain_in': round(esc['usdc_in'], 2),
        'onchain_out': round(esc['usdc_out'], 2),
        'funding_transfers': len(fundings),
        'unmatched_usd': round(funding_usd - escrowed_total, 2),
        'unmatched_transfers': len(fundings) - len(tasks),
        'top_requester_share_tasks': round(by_requester_n.most_common(1)[0][1] / len(tasks) * 100, 1),
        'top_requester_share_usd': round(
            by_requester_usd[by_requester_n.most_common(1)[0][0]] / escrowed_total * 100, 1),
        'captured_utc': cap['captured_utc'],
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    r = compute()
    print(f"taskmarket.dev, captured {r['captured_utc']}\n")
    print(f"  tasks the public API will show      {r['tasks']}")
    print(f"  distinct requesters                 {r['requesters']}")
    print(f"  total escrowed across those tasks   ${r['escrowed_total']:,.2f}")
    print(f"  completed                           {r['completed_tasks']} tasks, "
          f"${r['completed_escrowed']:,.2f}")
    print(f"  worker pool after the 7.5% fee      ${r['worker_pool']:,.2f}\n")
    print(f"  submissions to completed tasks      {r['submissions_to_completed']:,}")
    print(f"  submissions to every task           {r['submissions_all']:,}")
    print(f"  awards made                         {r['awards']}")
    print(f"  per completed task                  mean {r['mean_submissions']} / "
          f"median {r['median_submissions']} / max {r['max_submissions']} submissions\n")
    print(f"  EV of one submission                ${r['ev_per_submission']:.4f}")
    print(f"  EV against every task, not just     ${r['ev_per_submission_any']:.4f}")
    print(f"     the ones that completed")
    print(f"  share of submissions awarded        {r['award_rate_pct']}%\n")
    print(f"  escrow locked past deadline         {r['stuck_tasks']} tasks, "
          f"${r['stuck_usd']:,.2f}, {r['stuck_submissions']:,} submissions already made")
    print(f"  requesters that never completed     {r['never_completed_requesters']} of "
          f"{r['requesters']}, holding ${r['never_completed_usd']:,.2f} "
          f"across {r['never_completed_tasks']} tasks")
    print(f"  largest requester                   {r['top_requester_share_tasks']}% of tasks, "
          f"{r['top_requester_share_usd']}% of escrowed value\n")
    print(f"  on-chain escrow in / out            ${r['onchain_in']:,.2f} / ${r['onchain_out']:,.2f}")
    print(f"  reward-sized fundings on chain      {r['funding_transfers']}")
    print(f"  funded but not publicly listed      ${r['unmatched_usd']:,.2f} over "
          f"{r['unmatched_transfers']} transfers")

    if '--check' in sys.argv:
        bad = []
        for k, want in PUBLISHED.items():
            got = r[k]
            # Both sides are rounded to the same precision before comparison, so the only
            # tolerance needed is for binary float representation. A percentage tolerance
            # looks careful and is not: 0.5% of $2,473 is $12, which would wave through a
            # ten-dollar error, and a flat 0.02 would wave through a 27% error on a $0.07
            # figure. Neither can fail on the mistakes that actually happen here.
            tol = 1e-9 if isinstance(want, float) else 0
            if abs(got - want) > tol:
                bad.append(f'  {k}: published {want}, recomputed {got}')
        if bad:
            print('\nMISMATCH between published figures and the evidence:')
            print('\n'.join(bad))
            return 1
        print(f'\nall {len(PUBLISHED)} published figures match the evidence')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
