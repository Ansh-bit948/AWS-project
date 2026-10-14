"""Deterministic sparse role mining; all metrics come from input grants."""
from collections import Counter, defaultdict
from time import perf_counter
ENGINE_VERSION = '2.0.0'

def wsc(roles):
    return len(roles) + sum(len(r['users']) + len(r['permissions']) for r in roles)

def degree_percentiles(counts):
    frequencies = Counter(counts.values())
    total = len(counts)
    cumulative, ranks = 0, {}
    for value in sorted(frequencies):
        cumulative += frequencies[value]
        ranks[value] = round(cumulative / max(1, total), 6)
    return {key: ranks[value] for key, value in counts.items()}

def factor_roles(cohorts, max_steps=64):
    residual = [{'users': set(us), 'permissions': set(ps)} for ps, us in cohorts.items()]
    shared, steps = [], 0
    for _ in range(max_steps):
        support = defaultdict(list)
        for i, role in enumerate(residual):
            for p in sorted(role['permissions']):
                support[p].append(i)
        candidates = defaultdict(set)
        for p, ids in support.items():
            if len(ids) > 1:
                candidates[tuple(ids)].add(p)
        best = None
        for ids, ps in candidates.items():
            members = set().union(*(residual[i]['users'] for i in ids))
            saving = (len(ids) - 1) * len(ps) - len(members) - 1
            saving += sum(1 + len(residual[i]['users']) for i in ids if residual[i]['permissions'] == ps)
            candidate = (saving, tuple(sorted(ps)), ids, members, ps)
            if saving > 0 and (best is None or candidate[:3] > best[:3]):
                best = candidate
        if best is None:
            break
        _, _, ids, members, ps = best
        for i in ids:
            residual[i]['permissions'].difference_update(ps)
        shared.append({'users': members, 'permissions': ps})
        steps += 1
    return [r for r in residual + shared if r['permissions']], steps

def compute(dataset_id, rows, universe_users=None, universe_permissions=None, source_context=None):
    start = perf_counter()
    pairs = set(map(tuple, rows))
    by_user = {u: set() for u in (universe_users or [])}
    for u, p in sorted(pairs):
        by_user.setdefault(u, set()).add(p)
    all_permissions = set(universe_permissions or []) | {p for _, p in pairs}
    support = Counter(p for _, p in pairs)
    user_percentiles = degree_percentiles({u: len(ps) for u, ps in by_user.items()})
    permission_percentiles = degree_percentiles(support)
    users, perms, edges = len(by_user), len(all_permissions), len(pairs)
    cohorts = defaultdict(list)
    for u, ps in sorted(by_user.items()):
        if ps:
            cohorts[tuple(sorted(ps))].append(u)
    cohort_roles = [{'users': set(us), 'permissions': set(ps)} for ps, us in cohorts.items()]
    candidate, steps = factor_roles(cohorts)
    direct = [{'users': {u}, 'permissions': ps} for u, ps in by_user.items() if ps]
    choices = [('direct', direct), ('cohort', cohort_roles), ('greedy_support_factor', candidate)]
    method, selected = min(choices, key=lambda x: (wsc(x[1]), len(x[1]), x[0]))
    role_rows = []
    for i, r in enumerate(sorted(selected, key=lambda r: (-len(r['permissions']), tuple(sorted(r['permissions'])), tuple(sorted(r['users'])))), 1):
        role_rows.append({'role_id': f'R{i:04d}', 'users': sorted(r['users']), 'permissions': sorted(r['permissions']),
                          'user_count': len(r['users']), 'permission_count': len(r['permissions']), 'method': method})
    reconstructed, user_roles = defaultdict(set), defaultdict(list)
    for r in role_rows:
        for u in r['users']:
            reconstructed[u].update(r['permissions'])
            user_roles[u].append(r['role_id'])
    missing = sum(len(ps - reconstructed[u]) for u, ps in by_user.items())
    extra = sum(len(reconstructed[u] - ps) for u, ps in by_user.items())
    if missing or extra:
        raise RuntimeError('Role reconstruction violated exact coverage')
    for r in role_rows:
        r['coverage'] = 1.0
    risk, profiles = [], []
    source_context = source_context or {}
    source_users = source_context.get('users', {})
    source_permissions = source_context.get('permission_support', {})
    for u, ps in sorted(by_user.items()):
        rare = sorted((p for p in ps if support[p] / max(1, users) <= .05), key=lambda p: (support[p], p))
        density, rarity = len(ps) / max(1, perms), len(rare) / max(1, len(ps))
        percentile = user_percentiles[u]
        score = round(55 * rarity + 30 * density + 15 * percentile, 2)
        if rare or score >= 25:
            risk.append({'user_id': u, 'score': score, 'grant_count': len(ps), 'rare_permissions': rare,
                         'components': {'rarity_fraction': round(rarity, 5), 'density': round(density, 5),
                                        'user_degree_percentile': percentile},
                         'reasons': [f'{len(rare)} grants supported by <=5% of users',
                                     f'{density:.2%} of known permissions assigned',
                                     f'user grant count is at the {percentile:.0%} empirical percentile']})
        history = source_users.get(u)
        profiles.append({'user_id': u, 'observed_grants': len(ps), 'permission_density': round(density, 5),
                         'access_percentile': percentile,
                         'rare_grant_count': len(rare), 'attribute_status': 'Observed access history' if history else 'Not provided by dataset',
                         'access_history': history,
                         'role_ids': user_roles[u], 'cohort_role': user_roles[u][0] if user_roles[u] else None})
    risk.sort(key=lambda x: (-x['score'], x['user_id']))
    ua, pa = sum(r['user_count'] for r in role_rows), sum(r['permission_count'] for r in role_rows)
    return {'dataset_id': dataset_id, 'engine_version': ENGINE_VERSION,
            'counts': {'users': users, 'permissions': perms, 'assignments': edges, 'roles': len(role_rows)},
            'baseline': {'roles': len(direct), 'ua_edges': len(direct), 'pa_edges': edges, 'wsc': wsc(direct)},
            'cohort_baseline': {'roles': len(cohort_roles), 'wsc': wsc(cohort_roles)},
            'optimized': {'roles': len(role_rows), 'ua_edges': ua, 'pa_edges': pa, 'wsc': wsc(selected),
                          'coverage': (edges - missing) / edges if edges else 1.0, 'permission_loss': missing,
                          'overgrants': extra, 'factor_steps': steps, 'method': method},
            'risk_findings_total': len(risk),
            'risk_summary': {'high': sum(x['score'] >= 70 for x in risk),
                             'medium': sum(35 <= x['score'] < 70 for x in risk), 'review': sum(x['score'] < 35 for x in risk)},
            'roles': role_rows, 'profiles': profiles, 'risk_findings': risk,
            'permission_catalog': [{'permission_id': p, 'user_count': support[p], 'support': round(support[p] / max(1, users), 6),
                                   'prevalence_percentile': permission_percentiles[p],
                                   'source_active_users': source_permissions.get(p)} for p in sorted(all_permissions)],
            'performance': {'compute_ms': round((perf_counter() - start) * 1000, 3), 'representation': 'sparse Python sets; no dense U x P allocation'},
            'methodology': {'role_discovery': 'Exact access cohorts then bounded greedy support-signature factoring; best unit WSC candidate selected',
                            'optimization': 'Unit WSC = R + UA + PA; reconstructed edges checked for missing and extra grants; no global optimality claim',
                            'risk': '55% grant rarity fraction + 30% permission density + 15% user grant-count percentile; review signals, no confirmed-threat labels',
                            'attributes': 'Uses source-provided per-user access-change counts, last authorization time, and authorization delay when supplied; otherwise ACL structural features only. No HR attributes inferred',
                            'reinforcement_learning': 'Offline terminal Q-learning uses genuine administrator review feedback only; no simulated rewards',
                            'data_scope': 'Named access-control benchmark, not an operational ERP integration'}}
