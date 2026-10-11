"""Strict shared ingestion for actual access-control edge lists."""
import csv
import hashlib
import io
MAX_BYTES = 25 * 1024 * 1024
MAX_EDGES = 500_000

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
    for count, row in enumerate(reader, 1):
        if None in row:
            raise ValueError(f'Row {count + 1}: extra fields')
        u, p = (row.get(uc) or '').strip(), (row.get(pc) or '').strip()
        if not u or not p or len(u) > 200 or len(p) > 200:
            raise ValueError(f'Row {count + 1}: IDs must contain 1-200 characters')
        pairs.add((u, p))
        if len(pairs) > MAX_EDGES:
            raise ValueError('CSV exceeds the 500,000 distinct grant demo limit')
    if not pairs:
        raise ValueError('No assignment rows found')
    return sorted(pairs), {'sha256': hashlib.sha256(raw).hexdigest(), 'input_rows': count,
                           'distinct_edges': len(pairs), 'duplicates_removed': count - len(pairs)}
