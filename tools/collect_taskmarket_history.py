"""Sweep every task taskmarket.dev has ever published and every requester behind them.

The escrow measurement in this repo answers how much money left the contract. This answers
the question a worker actually has to make a decision with: given that I spend a submission
on a task, what is the chance anyone is ever paid for it, and what is a submission worth in
expectation. Both come from public endpoints and are recomputed rather than quoted.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = 'https://taskmarket.dev/api'
H = {'User-Agent': 'does-it-pay/1.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'evidence', 'taskmarket_history')
# Sweeping by status misses tasks: `status=open` returns only those whose submission window
# is still open, so it under-reports live tasks roughly fourfold. The four lifecycle phases
# partition every task, so the sweep walks those and keeps statuses only as a cross-check.
PHASES = ['active', 'in_review', 'awaiting_settlement', 'resolved']
STATUSES = ['open', 'claimed', 'worker_selected', 'completed', 'cancelled', 'expired',
            'disputed', 'review', 'appealing']
PAGE = 100


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == tries - 1:
                raise
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(2 * (i + 1))
    return None


def fetch(key, value):
    """Walk one filter to exhaustion. The cursor is authoritative; a short page is not."""
    tasks, cursor, pages = {}, None, 0
    while True:
        url = f'{API}/tasks?{key}={value}&limit={PAGE}' + (f'&cursor={cursor}' if cursor else '')
        d = get(url)
        if d is None:
            break
        if isinstance(d, dict) and d.get('code') == 'NOT_FOUND':
            break
        page = d.get('tasks') if isinstance(d, dict) else d
        if not isinstance(page, list):
            break
        for t in page:
            tasks[t['id']] = t
        pages += 1
        cursor = d.get('nextCursor') if isinstance(d, dict) else None
        if not cursor or not page:
            break
        if pages > 200:
            raise RuntimeError(f'{key}={value}: pagination did not terminate')
    print(f'  {key}={value:20s} {len(tasks):5d} tasks over {pages} pages', flush=True)
    return tasks


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.makedirs(OUT, exist_ok=True)
    all_tasks = {}
    for ph in PHASES:
        all_tasks.update(fetch('phase', ph))
    by_phase = len(all_tasks)
    for st in STATUSES:
        all_tasks.update(fetch('status', st))
    if len(all_tasks) != by_phase:
        print(f'  NOTE: the status sweep found {len(all_tasks) - by_phase} tasks the phase '
              f'sweep missed', flush=True)
    print(f'\n{len(all_tasks)} distinct tasks', flush=True)

    requesters = sorted({t['requester'].lower() for t in all_tasks.values()})
    print(f'{len(requesters)} distinct requesters; fetching stats', flush=True)
    rstats = {}
    for i, addr in enumerate(requesters):
        d = get(f'{API}/requester/{addr}/stats')
        if d and 'totalTasksCreated' in d:
            rstats[addr] = d
        if (i + 1) % 25 == 0:
            print(f'  {i + 1}/{len(requesters)}', flush=True)

    stamp = time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime())
    json.dump({'captured_utc': stamp, 'tasks': all_tasks, 'requester_stats': rstats},
              open(os.path.join(OUT, 'capture.json'), 'w', encoding='utf-8'), indent=1)
    print(f'\nwrote {OUT}/capture.json  ({len(all_tasks)} tasks, {len(rstats)} requesters)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
