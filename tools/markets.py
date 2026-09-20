"""Read-only probes for every earning marketplace that survived screening.

Nothing here claims, submits or spends. It answers two questions per market:
is there open work, and is the money behind it real?
"""
import json, os, time, urllib.request, urllib.error

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
BASE_RPC = 'https://mainnet.base.org'
USDC_BASE = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
STATE = os.path.join(os.path.dirname(__file__), '..', 'state')


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def rpc(method, params):
    req = urllib.request.Request(
        BASE_RPC,
        data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
        headers={'Content-Type': 'application/json', **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get('result')


def base_balances(address):
    """USDC (6dp) and ETH (18dp) held by an address on Base."""
    data = '0x70a08231' + address.lower().replace('0x', '').rjust(64, '0')
    usdc = rpc('eth_call', [{'to': USDC_BASE, 'data': data}, 'latest'])
    eth = rpc('eth_getBalance', [address, 'latest'])
    return (int(usdc, 16) / 1e6 if usdc and usdc != '0x' else 0.0,
            int(eth, 16) / 1e18 if eth else 0.0)


def taskmarket():
    """Open tasks. `free_slot` is the only thing that matters: the first five
    submissions to a bounty are free, every later one costs an x402 payment."""
    d = get_json('https://taskmarket.dev/api/tasks')
    out = []
    for t in d.get('tasks', []):
        if t.get('status') != 'open':
            continue
        subs = t.get('submissionCount') or 0
        out.append({
            'market': 'taskmarket', 'id': t['id'], 'ref': t.get('referenceCode'),
            'reward_usdc': float(t.get('reward') or 0) / 1e6,
            'net_usdc': float(t.get('netReward') or 0) / 1e6,
            'submissions': subs, 'free_slot': subs < 5,
            'mode': t.get('mode'), 'phase': t.get('phase'),
            'expires': t.get('expiryTime'), 'escrow_tx': t.get('escrowTxHash'),
            'title': (t.get('description') or '').strip().lstrip('#').strip()[:90],
        })
    return out


def bountybook():
    """Open jobs, annotated with whether the poster can actually pay."""
    d = get_json('https://api.bountybook.ai/jobs?status=open&limit=100')
    jobs = d.get('jobs', [])
    funded = {}
    for j in jobs:
        p = j.get('poster_address')
        if p and p not in funded:
            try:
                funded[p] = base_balances(p)[0]
            except Exception:
                funded[p] = None
    return [{
        'market': 'bountybook', 'id': j['id'], 'reward_usdc': float(j.get('budget_usdc') or 0),
        'job_type': j.get('job_type'), 'poster': j.get('poster_address'),
        'poster_usdc': funded.get(j.get('poster_address')),
        'title': str(j.get('title'))[:90],
    } for j in jobs]


def superteam(api_key):
    req = urllib.request.Request(
        'https://superteam.fun/api/agents/listings/live?take=50',
        headers={'Authorization': f'Bearer {api_key}', **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    items = d if isinstance(d, list) else d.get('listings', [])
    return [{
        'market': 'superteam', 'id': x.get('id'), 'slug': x.get('slug'),
        'reward_usdc': x.get('rewardAmount'), 'token': x.get('token'),
        'deadline': x.get('deadline'), 'type': x.get('type'),
        'title': str(x.get('title'))[:90],
    } for x in items]


def agentpact_needs():
    d = get_json('https://api.agentpact.xyz/api/needs?limit=50')
    needs = d if isinstance(d, list) else d.get('needs', [])
    out = []
    for n in needs:
        lo, hi = n.get('budget_min'), n.get('budget_max')
        out.append({'market': 'agentpact', 'id': n.get('id'),
                    'reward_usdc': float(hi or lo or 0),
                    'title': str(n.get('title'))[:90]})
    return out


PROBES = {'taskmarket': taskmarket, 'bountybook': bountybook, 'agentpact': agentpact_needs}
