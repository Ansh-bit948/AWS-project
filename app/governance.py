"""Explainable review, authorization, and learning from actual administrator feedback."""
import hashlib
import json
from collections import Counter, defaultdict

def recommendations(analysis, decisions):
    latest = {(d['user_id'], d['permission_id']): d for d in decisions}
    actions = {}
    for r in analysis['risk_findings']:
        for p in r['rare_permissions']:
            actions[(r['user_id'], p)] = {'user_id': r['user_id'], 'permission_id': p, 'status': 'pending_review',
                                         'risk_score': r['score'], 'reason': 'Observed grant has <=5% user support; rarity does not establish unnecessary access'}
    for key, d in latest.items():
        actions.setdefault(key, {'user_id': key[0], 'permission_id': key[1], 'reason': 'Previously reviewed source grant', 'risk_score': None})
        actions[key]['status'] = d['decision']
    rows = sorted(actions.values(), key=lambda x: (x['status'] != 'revoke', -(x.get('risk_score') or 0), x['user_id'], x['permission_id']))
    return {'dataset_id': analysis['dataset_id'], 'recommendations': rows, 'approval_required': True,
            'note': 'Removal affects this application policy only. Retain restores a removed source grant. Source data remain immutable.'}

def authorize(analysis, user_id, permission_id):
    roles = [r['role_id'] for r in analysis['roles'] if user_id in r['users'] and permission_id in r['permissions']]
    return {'allowed': bool(roles), 'matching_roles': roles, 'policy_version': analysis.get('policy_version', 1),
            'scope': 'Application authorization against selected benchmark policy'}

def feedback_state(profile):
    return f"rare:{min(4, profile['rare_grant_count'])}|density:{min(3, int(profile['permission_density'] * 4))}"

def train_feedback(analysis, audit, episodes=500):
    profiles = {p['user_id']: p for p in analysis['profiles']}
    latest = {}
    for event in sorted(audit, key=lambda x: x['created_at']):
        if event['action'] != 'permission_decision':
            continue
        d = event['details']
        if isinstance(d, str):
            d = json.loads(d)
        if d.get('purpose', 'review') != 'review' or d.get('decision') not in ('revoke', 'retain'):
            continue
        if d.get('user_id') in profiles and d.get('state'):
            latest[(d['user_id'], d['permission_id'])] = d
    records = sorted(latest.values(), key=lambda d: (d['user_id'], d['permission_id']))
    if len(records) < 5 or len({d['user_id'] for d in records}) < 2:
        raise ValueError('Need at least 5 genuine administrator reviews across 2 users. Validation operations and simulated feedback do not count.')
    users = sorted({d['user_id'] for d in records}, key=lambda u: hashlib.sha256(u.encode()).hexdigest())
    heldout = set(users[:max(1, len(users) // 5)])
    training = [d for d in records if d['user_id'] not in heldout]
    testing = [d for d in records if d['user_id'] in heldout]
    q = defaultdict(lambda: [0.0, 0.0])
    counts = Counter((d['state'], 1 if d['decision'] == 'revoke' else 0) for d in training)
    # Terminal observed transitions; gamma=0. Only actual approved actions receive reward.
    for i in range(max(1, min(int(episodes), 10000))):
        d = training[i % len(training)]
        action = 1 if d['decision'] == 'revoke' else 0
        q[d['state']][action] += .15 * (1.0 - q[d['state']][action])
    correct, evaluated = 0, 0
    for d in testing:
        values = q.get(d['state'])
        if values is not None and values[0] != values[1]:
            evaluated += 1
            correct += int((values[1] > values[0]) == (d['decision'] == 'revoke'))
    policy = []
    for p in analysis['profiles']:
        state = feedback_state(p)
        values = q.get(state)
        action = 'review' if values is None or values[0] == values[1] else ('propose_revoke' if values[1] > values[0] else 'retain')
        policy.append({'user_id': p['user_id'], 'state': state, 'recommendation': action,
                       'q_values': [round(v, 6) for v in values] if values is not None else None,
                       'approval_required': True, 'automated_change': False})
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    return {'episodes': max(1, min(int(episodes), 10000)), 'model': 'offline terminal tabular Q-learning (gamma=0; contextual bandit)',
            'feedback_sha256': digest, 'feedback_records': len(records), 'training_records': len(training), 'heldout_records': len(testing),
            'action_counts': {'retain': sum(v for (s,a),v in counts.items() if a == 0), 'propose_revoke': sum(v for (s,a),v in counts.items() if a == 1)},
            'q_table': dict(q), 'recommendations': policy,
            'evaluation': {'split': 'user-disjoint 20% holdout (minimum one user)', 'agreement': correct / evaluated if evaluated else None,
                           'evaluated_records': evaluated, 'abstained_records': len(testing) - evaluated,
                           'limit': 'Agreement with recorded administrator actions; no safety, threat accuracy, or optimality claim'},
            'reward': 'Actual human approval rewards its observed action; no synthetic rewards or feedback'}
