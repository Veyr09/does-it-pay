"""Price a taskmarket.dev task before working on it.

Answers the one question the task page does not: given this reward, this many submissions
already in, and this requester's history of actually paying, what is a submission worth?

    python tools/is_it_worth_it.py 0xea9b5bd5…          # one task
    python tools/is_it_worth_it.py --all                # every open task, ranked

Every input is a public endpoint and the platform-wide base rates come from the frozen
capture in data/evidence/taskmarket_history/, recomputed by tools/taskmarket_economics.py.
"""
import calendar
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = 'https://taskmarket.dev/api'
H = {'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORM_FEE_BPS = 750
# Platform-wide base rates, from tools/taskmarket_economics.py over the frozen capture.
BASE_AWARDS_PER_TASK = 540 / 323      # mean winners on a completed task
BASE_EV_PER_SUBMISSION = 0.0749
# The platform mean is 1.67 winners a task, but it is a mixture: some requesters split a
# bounty three ways and others always pick exactly one. Using the mixture for a requester
# whose every task has a single winner overstates a submission by about 70 per cent, so
# where a requester has a record of their own, use it.
MIN_TASKS_FOR_OWN_RATE = 3
# A task still open attracts more submissions before it closes. Median submissions on a
# completed task is 29, so a task sitting at 3 today is not a 3-way race.
MEDIAN_FINAL_SUBMISSIONS = 29


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {'_http': e.code}


def unwrap(d):
    return d.get('data', d) if isinstance(d, dict) else d


def requester_awards_per_task(requester):
    """Mean winners on this requester's own completed tasks, if they have enough of a record.

    Read from their completed tasks rather than assumed: a requester who always picks one
    winner is a very different proposition from one who splits three ways.
    """
    seen, cursor, pages = {}, None, 0
    while pages < 12:
        url = f'{API}/tasks?status=completed&limit=100' + (f'&cursor={cursor}' if cursor else '')
        d = unwrap(get(url))
        rows = (d.get('tasks') if isinstance(d, dict) else d) or []
        for t in rows:
            if (t.get('requester') or '').lower() == requester:
                seen[t['id']] = t              # dedupe: a repeated page must not be counted twice
        cursor = d.get('nextCursor') if isinstance(d, dict) else None
        pages += 1
        if not cursor or not rows:
            break
    awarded = [t.get('awardCount') or 0 for t in seen.values() if (t.get('awardCount') or 0) > 0]
    if len(awarded) < MIN_TASKS_FOR_OWN_RATE:
        return None, len(awarded)
    return sum(awarded) / len(awarded), len(awarded)


def price(task):
    """Expected value of adding one submission to this task, and why."""
    reward = int(task.get('reward') or 0) / 1e6
    subs_now = task.get('submissionCount') or 0
    requester = task['requester'].lower()
    rs = unwrap(get(f'{API}/requester/{requester}/stats')) or {}
    created = rs.get('totalTasksCreated', 0)
    completed = rs.get('completedCount', 0)
    own_rate, own_n = requester_awards_per_task(requester)
    awards_per_task = own_rate if own_rate else BASE_AWARDS_PER_TASK

    # A requester with no history gets the platform base rate rather than 0% or 100%, with
    # one prior completion's worth of weight. Their own record dominates once they have one.
    PRIOR_WEIGHT = 1.0
    PLATFORM_COMPLETION_RATE = 323 / 442
    p_settles = ((completed + PRIOR_WEIGHT * PLATFORM_COMPLETION_RATE)
                 / (created + PRIOR_WEIGHT)) if created else PLATFORM_COMPLETION_RATE

    final_subs = max(subs_now + 1, MEDIAN_FINAL_SUBMISSIONS)
    pool = reward * (1 - PLATFORM_FEE_BPS / 10000)
    p_win = min(1.0, awards_per_task / final_subs)
    ev = p_settles * p_win * (pool / max(1.0, awards_per_task))
    return {
        'ref': task.get('referenceCode'), 'id': task['id'], 'reward': reward,
        'subs_now': subs_now, 'assumed_final_subs': final_subs,
        'requester': requester, 'requester_created': created, 'requester_completed': completed,
        'p_settles': p_settles, 'p_win_if_settles': p_win, 'pool': pool, 'ev': ev,
        'awards_per_task': round(awards_per_task, 2), 'awards_basis': 
            f'this requester, {own_n} completed tasks' if own_rate else 'platform mean',
        'expiry': task.get('expiryTime'), 'status': task.get('status'),
    }


def show(r):
    verdict = ('worth it' if r['ev'] >= BASE_EV_PER_SUBMISSION * 3 else
               'about average' if r['ev'] >= BASE_EV_PER_SUBMISSION else 'below the base rate')
    days = ''
    if r['expiry']:
        try:
            left = (calendar.timegm(time.strptime(r['expiry'][:19], '%Y-%m-%dT%H:%M:%S'))
                    - time.time()) / 86400
            days = f"  closes in {left:.1f}d" if left > 0 else '  CLOSED'
        except ValueError:
            pass
    print(f"{r['ref']}  ${r['reward']:.2f}  {r['status']}{days}")
    print(f"  requester {r['requester']}")
    if r['requester_created']:
        print(f"    has created {r['requester_created']} tasks and completed "
              f"{r['requester_completed']}"
              + ('   <- has never paid anyone' if not r['requester_completed'] else ''))
    else:
        print("    no history at all; scored at the platform completion rate")
    print(f"  {r['subs_now']} submissions in; priced against {r['assumed_final_subs']} at close")
    print(f"  P(task ever settles) {r['p_settles']*100:5.1f}%   "
          f"P(you are among the winners | it settles) {r['p_win_if_settles']*100:5.1f}%")
    print(f"  worker pool ${r['pool']:.2f}, {r['awards_per_task']:.2f} winners "
          f"({r['awards_basis']})")
    print(f"  EXPECTED VALUE OF ONE SUBMISSION  ${r['ev']:.4f}   "
          f"({verdict}; platform base rate ${BASE_EV_PER_SUBMISSION:.4f})\n")


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--all' in sys.argv:
        tasks = {}
        for key, val in [('phase', 'active'), ('status', 'open')]:
            d = unwrap(get(f'{API}/tasks?{key}={val}&limit=100'))
            for t in (d.get('tasks') if isinstance(d, dict) else d) or []:
                tasks[t['id']] = t
        rows = sorted((price(t) for t in tasks.values()), key=lambda r: -r['ev'])
        print(f'{len(rows)} open tasks, best expected value first\n')
        for r in rows:
            show(r)
        if rows:
            print(f'total expected value of submitting to every open task: '
                  f'${sum(r["ev"] for r in rows):.2f}')
        return 0
    if not args:
        print(__doc__)
        return 2
    for tid in args:
        d = unwrap(get(f'{API}/tasks/{tid}'))
        if not d or '_http' in d:
            print(f'{tid}: not found')
            return 1
        show(price(d))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
