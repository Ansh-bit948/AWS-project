"""Strict shared ingestion for actual access-control edge lists."""
import csv
import hashlib
import io
import math
from datetime import datetime
MAX_BYTES = 25 * 1024 * 1024
MAX_EDGES = 500_000

STRUCTURE_FIELDS = ('derived_user_assignment_count', 'derived_permission_user_count',
                    'derived_user_access_density', 'derived_permission_prevalence',
                    'derived_user_degree_percentile', 'derived_permission_degree_percentile')

def _percentiles(counts):
    from collections import Counter
    frequencies = Counter(counts.values())
    total, cumulative, ranks = len(counts), 0, {}
    for value in sorted(frequencies):
        cumulative += frequencies[value]
        ranks[value] = round(cumulative / max(1, total), 6)
    return {key: ranks[value] for key, value in counts.items()}

def parse_csv(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('CSV exceeds the 25 MiB demo limit')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    fields = {x.strip().lower(): x for x in (reader.fieldnames or [])}
    uc = next((fields[x] for x in ('user_id', 'user', 'uid') if x in fields), None)
    pc = next((fields[x] for x in ('permission_id', 'permission', 'resource_id', 'rid') if x in fields), None)
    if not uc or not pc:
        raise ValueError('Required columns: user_id,permission_id')
    pairs, count = set(), 0
    optional = ('last_request_date', 'last_authorization_date', 'grant_event_count',
                'remove_event_count', 'user_active_grants', 'user_access_change_events',
                'permission_active_users', 'authorization_delay_seconds')
    present = [name for name in optional if name in fields]
    if present and len(present) != len(optional):
        raise ValueError('Observed-history enrichment must include all eight documented fields')
    structure_present = [name for name in STRUCTURE_FIELDS if name in fields]
    if structure_present and len(structure_present) != len(STRUCTURE_FIELDS):
        raise ValueError('Derived matrix enrichment must include all six documented fields')
    pair_metadata = {}
    permission_reports = {}
    structure_reports = {}
    for count, row in enumerate(reader, 1):
        if None in row:
            raise ValueError(f'Row {count + 1}: extra fields')
        u, p = (row.get(uc) or '').strip(), (row.get(pc) or '').strip()
        if not u or not p or len(u) > 200 or len(p) > 200:
            raise ValueError(f'Row {count + 1}: IDs must contain 1-200 characters')
        pairs.add((u, p))
        if structure_present:
            try:
                values = {
                    'derived_user_assignment_count': int(row[fields[STRUCTURE_FIELDS[0]]]),
                    'derived_permission_user_count': int(row[fields[STRUCTURE_FIELDS[1]]]),
                    'derived_user_access_density': float(row[fields[STRUCTURE_FIELDS[2]]]),
                    'derived_permission_prevalence': float(row[fields[STRUCTURE_FIELDS[3]]]),
                    'derived_user_degree_percentile': float(row[fields[STRUCTURE_FIELDS[4]]]),
                    'derived_permission_degree_percentile': float(row[fields[STRUCTURE_FIELDS[5]]]),
                }
                if (any(not math.isfinite(v) for v in values.values()) or
                        min(values.values()) < 0 or
                        any(values[name] > 1 for name in STRUCTURE_FIELDS[2:])):
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f'Row {count + 1}: invalid derived matrix features')
            key = (u, p)
            if key in structure_reports and structure_reports[key] != values:
                raise ValueError(f'Row {count + 1}: duplicate assignment has conflicting derived features')
            structure_reports[key] = values
        if present:
            try:
                requested = datetime.strptime(row[fields['last_request_date']], '%Y-%m-%d %H:%M:%S')
                authorized = datetime.strptime(row[fields['last_authorization_date']], '%Y-%m-%d %H:%M:%S')
                grant_events = int(row[fields['grant_event_count']])
                remove_events = int(row[fields['remove_event_count']])
                active_grants = int(row[fields['user_active_grants']])
                changes = int(row[fields['user_access_change_events']])
                permission_users = int(row[fields['permission_active_users']])
                delay = float(row[fields['authorization_delay_seconds']])
                if min(grant_events, remove_events, active_grants, changes, permission_users) < 0 or delay < 0:
                    raise ValueError
                if (authorized - requested).total_seconds() != delay:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f'Row {count + 1}: invalid observed history attributes')
            values = {'last_request_date': row[fields['last_request_date']],
                      'last_authorization_date': row[fields['last_authorization_date']],
                      'grant_event_count': grant_events, 'remove_event_count': remove_events,
                      'user_active_grants': active_grants, 'user_access_change_events': changes,
                      'permission_active_users': permission_users,
                      'authorization_delay_seconds': delay}
            key = (u, p)
            if key in pair_metadata and pair_metadata[key] != values:
                raise ValueError(f'Row {count + 1}: duplicate grant has conflicting observed history')
            pair_metadata[key] = values
            if p in permission_reports and permission_reports[p] != permission_users:
                raise ValueError(f'Conflicting permission support attributes for {p}')
            permission_reports[p] = permission_users
        if len(pairs) > MAX_EDGES:
            raise ValueError('CSV exceeds the 500,000 distinct grant demo limit')
    if not pairs:
        raise ValueError('No assignment rows found')
    quality = {'sha256': hashlib.sha256(raw).hexdigest(), 'input_rows': count,
               'distinct_edges': len(pairs), 'duplicates_removed': count - len(pairs),
               'attribute_columns': present or structure_present}
    if structure_present:
        users = {u for u, _ in pairs}
        permissions = {p for _, p in pairs}
        user_counts, permission_counts = {}, {}
        for u, p in pairs:
            user_counts[u] = user_counts.get(u, 0) + 1
            permission_counts[p] = permission_counts.get(p, 0) + 1
        user_percentiles = _percentiles(user_counts)
        permission_percentiles = _percentiles(permission_counts)
        for u, p in pairs:
            report = structure_reports[(u, p)]
            expected = (user_counts[u], permission_counts[p],
                        round(user_counts[u] / len(permissions), 8),
                        round(permission_counts[p] / len(users), 8),
                        user_percentiles[u], permission_percentiles[p])
            observed = tuple(report[name] for name in STRUCTURE_FIELDS)
            if (observed[0:2] != expected[0:2] or
                    any(abs(a - b) > 0.00000051 for a, b in zip(observed[2:], expected[2:]))):
                raise ValueError(f'Derived matrix features do not match the actual assignments ({u}, {p})')
        quality['validated_derived_columns'] = len(structure_present)
    if present:
        actual_user_counts = {}
        actual_permission_counts = {}
        for u, p in pairs:
            actual_user_counts[u] = actual_user_counts.get(u, 0) + 1
            actual_permission_counts[p] = actual_permission_counts.get(p, 0) + 1
        user_rows = {}
        for u, p in pairs:
            m = pair_metadata[(u, p)]
            profile = user_rows.setdefault(u, {'access_change_events': m['user_access_change_events'],
                'active_grants_reported': m['user_active_grants'], 'last_authorized_at': m['last_authorization_date'],
                'authorization_delay_seconds': [], 'grant_events_for_active_pairs': 0,
                'removal_events_for_active_pairs': 0})
            if profile['access_change_events'] != m['user_access_change_events'] or profile['active_grants_reported'] != m['user_active_grants']:
                raise ValueError(f'Conflicting user-level history attributes for {u}')
            profile['last_authorized_at'] = max(profile['last_authorized_at'], m['last_authorization_date'])
            profile['authorization_delay_seconds'].append(m['authorization_delay_seconds'])
            profile['grant_events_for_active_pairs'] += m['grant_event_count']
            profile['removal_events_for_active_pairs'] += m['remove_event_count']
        for u, profile in user_rows.items():
            if profile['active_grants_reported'] != actual_user_counts[u]:
                raise ValueError(f'Observed active grant count does not match rows for {u}')
            delays = profile.pop('authorization_delay_seconds')
            profile['mean_authorization_delay_seconds'] = round(sum(delays) / len(delays), 3)
        for p, actual in actual_permission_counts.items():
            if permission_reports[p] != actual:
                raise ValueError(f'Observed permission support does not match rows for {p}')
        quality['profiled_users'] = len(user_rows)
        quality['profiled_permissions'] = len(actual_permission_counts)
        quality['source_context'] = {'users': user_rows, 'permission_support': actual_permission_counts}
    return sorted(pairs), quality
