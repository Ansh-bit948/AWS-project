"""Build feature-rich CSVs from real HP Labs role-mining UPA matrices.

The input matrices are genuine two-column user-permission edge lists. The six
additional columns are deterministic graph statistics computed from those
edges; they are not source-record attributes. See test_sets/README.md.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "test_sets"
EXPECTED = {
    "americas_small": (3477, 1587, 105205),
    "apj": (2044, 1164, 6841),
    "healthcare": (46, 46, 1486),
    "domino": (79, 231, 730),
    "firewall2": (325, 590, 36428),
}
FIELDS = [
    "user_id",
    "permission_id",
    "derived_user_assignment_count",
    "derived_permission_user_count",
    "derived_user_access_density",
    "derived_permission_prevalence",
    "derived_user_degree_percentile",
    "derived_permission_degree_percentile",
]


def percentile_ranks(counts: Counter[str]) -> dict[str, float]:
    frequencies = Counter(counts.values())
    n = len(counts)
    cumulative = 0
    ranks: dict[int, float] = {}
    for value in sorted(frequencies):
        cumulative += frequencies[value]
        ranks[value] = round(cumulative / n, 6)
    return {key: ranks[value] for key, value in counts.items()}


def main() -> None:
    manifest: dict[str, object] = {
        "source_collection": "HP Labs real-world role-mining access-control matrices",
        "repository": "https://github.com/carblu/rolemining/tree/main/datasets",
        "research_reference": "https://doi.org/10.1145/1387309.1387312",
        "fields": FIELDS,
        "field_semantics": {
            "user_id": "Source's anonymized user identifier",
            "permission_id": "Source's permission/resource identifier",
            "derived_user_assignment_count": "Number of distinct permissions assigned to this user in this matrix",
            "derived_permission_user_count": "Number of distinct users assigned this permission in this matrix",
            "derived_user_access_density": "User assignment count divided by source permission count",
            "derived_permission_prevalence": "Permission user count divided by source user count",
            "derived_user_degree_percentile": "Empirical percentile rank of the user's assignment count among source users",
            "derived_permission_degree_percentile": "Empirical percentile rank of the permission's user count among source permissions",
        },
        "datasets": {},
    }

    for name, expected in EXPECTED.items():
        source = DATA / f"{name}.source.txt"
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        pairs: set[tuple[str, str]] = set()
        for line_no, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
            parts = line.split()
            if not parts:
                continue
            if len(parts) != 2:
                raise ValueError(f"{source.name}:{line_no}: expected two source IDs")
            pairs.add((parts[0], parts[1]))

        users = Counter(u for u, _ in pairs)
        permissions = Counter(p for _, p in pairs)
        observed = (len(users), len(permissions), len(pairs))
        if observed != expected:
            raise ValueError(f"{name}: source dimensions {observed} != published {expected}")
        user_pct = percentile_ranks(users)
        permission_pct = percentile_ranks(permissions)
        output = DATA / f"{name}.csv"
        with output.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for user_id, permission_id in sorted(pairs):
                uc, pc = users[user_id], permissions[permission_id]
                writer.writerow({
                    "user_id": user_id,
                    "permission_id": permission_id,
                    "derived_user_assignment_count": uc,
                    "derived_permission_user_count": pc,
                    "derived_user_access_density": f"{uc / len(permissions):.8f}",
                    "derived_permission_prevalence": f"{pc / len(users):.8f}",
                    "derived_user_degree_percentile": f"{user_pct[user_id]:.6f}",
                    "derived_permission_degree_percentile": f"{permission_pct[permission_id]:.6f}",
                })
        manifest["datasets"][name] = {
            "source_file": source.name,
            "csv_file": output.name,
            "source_sha256": digest,
            "users": len(users),
            "permissions": len(permissions),
            "assignments": len(pairs),
        }

    (DATA / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
