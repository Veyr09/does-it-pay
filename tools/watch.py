"""Watch every surviving marketplace for work that is worth doing.

Emits one stdout line per event. It never claims, submits or spends: the whole point is
to turn "is there funded work right now" into a notification, and leave the decision to
act deliberate.

Event lines:
  NEW  <market> <reward> <free_slot> <id> :: <title>
  GONE <market> <id>
  INFO <text>
"""
import json, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(__file__))
import markets

STATE = os.path.join(os.path.dirname(__file__), '..', 'state')
os.makedirs(STATE, exist_ok=True)
SEEN = os.path.join(STATE, 'seen.json')
ALERTS = os.path.join(STATE, 'alerts.jsonl')

SUPERTEAM_KEY = None
reg = os.path.join(os.path.dirname(__file__), '..', 'secrets', 'agent_reg.json')
if os.path.exists(reg):
    SUPERTEAM_KEY = json.load(open(reg)).get('apiKey')


def load_seen():
    if os.path.exists(SEEN):
        try:
            return json.load(open(SEEN))
        except Exception:
            pass
    return {}


def save_seen(d):
    tmp = SEEN + '.tmp'
    json.dump(d, open(tmp, 'w'))
    os.replace(tmp, SEEN)


def worth_reporting(row):
    """Filter out the noise the audit already disqualified."""
    r = float(row.get('reward_usdc') or 0)
    if row['market'] == 'bountybook':
        # the queue is real only if the poster can actually pay
        return r >= 1.0 and (row.get('poster_usdc') or 0) >= r
    if row['market'] == 'taskmarket':
        return r >= 1.0
    if row['market'] == 'agentpact':
        return r >= 1.0
    return r >= 1.0


def collect():
    rows = []
    for name, fn in markets.PROBES.items():
        try:
            rows += fn()
        except Exception as e:
            print(f'INFO probe {name} failed: {type(e).__name__} {e}', flush=True)
    if SUPERTEAM_KEY:
        try:
            rows += markets.superteam(SUPERTEAM_KEY)
        except Exception as e:
            print(f'INFO probe superteam failed: {type(e).__name__} {e}', flush=True)
    return rows


def main(interval=180):
    seen = load_seen()
    first = not seen
    while True:
        try:
            rows = collect()
            now = {f"{r['market']}:{r['id']}": r for r in rows}
            for k, r in now.items():
                if k in seen:
                    continue
                seen[k] = {'ts': time.time(), 'reward': r.get('reward_usdc')}
                if first or not worth_reporting(r):
                    continue
                line = (f"NEW {r['market']} ${float(r.get('reward_usdc') or 0):.2f} "
                        f"free={r.get('free_slot')} {r['id']} :: {str(r.get('title'))[:80]}")
                print(line, flush=True)
                with open(ALERTS, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'ts': time.time(), 'event': 'new', 'row': r}) + '\n')
            for k in list(seen):
                if k not in now and not seen[k].get('gone'):
                    seen[k]['gone'] = time.time()
            save_seen(seen)
            if first:
                funded = [r for r in rows if worth_reporting(r)]
                print(f"INFO baseline: {len(rows)} rows, {len(funded)} pass the funding filter", flush=True)
                for r in funded[:10]:
                    print(f"INFO  funded ${float(r.get('reward_usdc') or 0):.2f} {r['market']} "
                          f"free={r.get('free_slot')} :: {str(r.get('title'))[:70]}", flush=True)
                first = False
        except Exception:
            print('INFO watcher error: ' + traceback.format_exc().splitlines()[-1], flush=True)
        time.sleep(interval)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 180)
