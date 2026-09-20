"""Generate the two JSON payloads the static board renders, then copy them into the repo.

Panel 1 — funded agent work: every open task on every marketplace that survived screening,
annotated with whether the poster can actually pay. That annotation is the whole point; it
is one RPC call and nobody publishes it.

Panel 2 — tokenised equities: live basis, the Token-2022 multiplier that explains most of
it, the adjusted basis, each ticker's own baseline, and the price impact of actually
transacting at the quoted price.
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import markets                      # noqa: E402
import basis_board                  # noqa: E402
import is_it_worth_it               # noqa: E402

REPO = os.environ.get('DOES_IT_PAY_REPO',
                      r'C:\Users\meiz\AppData\Local\Temp\claude\does-it-pay')
OUT_LOCAL = os.path.join(ROOT, 'site', 'data')


def work_panel():
    rows, errors = [], []
    for name, fn in markets.PROBES.items():
        try:
            rows += fn()
        except Exception as e:
            errors.append(f'{name}: {type(e).__name__}')
    out = []
    for r in rows:
        reward = float(r.get('reward_usdc') or 0)
        if reward < 0.5:
            continue                      # $0.01 reputation dust is not work
        funded = None
        if r['market'] == 'bountybook':
            funded = (r.get('poster_usdc') or 0) >= reward
        elif r['market'] == 'taskmarket':
            funded = bool(r.get('escrow_tx'))     # escrow tx on Base, verifiable
        row = {
            'market': r['market'], 'id': str(r.get('id')),
            'ref': r.get('ref'),
            'reward_usdc': round(reward, 2),
            'funded': funded,
            'free_slot': r.get('free_slot'),
            'submissions': r.get('submissions'),
            'deadline': r.get('expires') or r.get('deadline'),
            'title': (r.get('title') or '').strip().replace('\n', ' ')[:120],
        }
        if r['market'] == 'taskmarket' and r.get('requester'):
            # The reward is what the task advertises. This is what entering it is worth,
            # priced against the requester's own record of ever paying anyone.
            try:
                pr = is_it_worth_it.price({'id': r['id'], 'referenceCode': r.get('ref'),
                                           'reward': int(round(reward * 1e6)),
                                           'submissionCount': r.get('submissions') or 0,
                                           'requester': r['requester'],
                                           'expiryTime': r.get('expires'),
                                           'status': r.get('status')})
                row.update({'ev_usd': round(pr['ev'], 4),
                            'p_settles': round(pr['p_settles'], 4),
                            'requester_created': pr['requester_created'],
                            'requester_completed': pr['requester_completed']})
            except Exception as e:
                errors.append(f"ev {r.get('ref')}: {type(e).__name__}")
        out.append(row)
    out.sort(key=lambda r: (r['funded'] is not True, -(r.get('ev_usd') or 0),
                            -r['reward_usdc']))
    return {'generated_at': datetime.now(timezone.utc).isoformat(),
            'errors': errors,
            'totals': {
                'open': len(out),
                'advertised_usd': round(sum(r['reward_usdc'] for r in out), 2),
                'funded_usd': round(sum(r['reward_usdc'] for r in out
                                        if r['funded'] is True), 2),
                'board_ev_usd': round(sum(r.get('ev_usd') or 0 for r in out), 4),
                'base_ev_usd': is_it_worth_it.BASE_EV_PER_SUBMISSION},
            'rows': out}


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.makedirs(OUT_LOCAL, exist_ok=True)
    payloads = {}

    try:
        payloads['work.json'] = work_panel()
        t = payloads['work.json']['totals']
        print(f"work panel: {t['open']} open, ${t['advertised_usd']:,.2f} advertised, "
              f"${t['funded_usd']:,.2f} demonstrably funded", flush=True)
    except Exception as e:
        print(f'work panel failed: {type(e).__name__}: {e}', flush=True)

    try:
        payloads['basis.json'] = basis_board.build()
        print(f"basis panel: {len(payloads['basis.json']['rows'])} tickers", flush=True)
    except Exception as e:
        print(f'basis panel failed: {type(e).__name__}: {e}', flush=True)

    for name, data in payloads.items():
        with open(os.path.join(OUT_LOCAL, name), 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))

    repo_data = os.path.join(REPO, 'docs', 'data')
    if os.path.isdir(os.path.join(REPO, 'docs')):
        os.makedirs(repo_data, exist_ok=True)
        for name in payloads:
            shutil.copy2(os.path.join(OUT_LOCAL, name), os.path.join(repo_data, name))
        print(f'copied {len(payloads)} payloads into {repo_data}', flush=True)
    return 0 if len(payloads) == 2 else 1


if __name__ == '__main__':
    raise SystemExit(main())
