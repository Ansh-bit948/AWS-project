"""Build import-ready year-end snapshots from the genuine UCI Amazon access history."""
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/amazon_access_history.csv"
OUTPUT = ROOT / "test_sets"
CHECKPOINTS = [datetime(year, 12, 31, 23, 59, 59) for year in range(2006, 2011)]
SOURCE_URL = "https://archive.ics.uci.edu/dataset/216/amazon+access+samples"
DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/216/amazon+access+samples.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing source history: {SOURCE}; download the official UCI archive first.")
    OUTPUT.mkdir(exist_ok=True)
    events = []
    invalid = read = 0
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            read += 1
            try:
                timestamp = datetime.strptime(row["AUTHORIZATION_DATE"], "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError, KeyError):
                invalid += 1
                continue
            user = (row.get("LOGIN") or "").strip()
            permission = (row.get("TARGET_NAME") or "").strip()
            action = row.get("ACTION")
            if not user or not permission or action not in ("add_access", "remove_access"):
                invalid += 1
                continue
            events.append((timestamp, read, user, permission, action))
    events.sort(key=lambda event: (event[0], event[1]))

    active = set()
    snapshots = []
    checkpoints = list(CHECKPOINTS)

    def write_snapshot(cutoff: datetime) -> None:
        pairs = sorted(active)
        path = OUTPUT / f"amazon_access_snapshot_{cutoff.year}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["user_id", "permission_id"])
            writer.writerows(pairs)
        snapshots.append({
            "file": path.name,
            "snapshot_as_of": cutoff.isoformat(),
            "users": len({user for user, _ in pairs}),
            "permissions": len({permission for _, permission in pairs}),
            "grants": len(pairs),
            "sha256": sha256(path),
        })

    for timestamp, _, user, permission, action in events:
        while checkpoints and checkpoints[0] < timestamp:
            write_snapshot(checkpoints.pop(0))
        pair = (user, permission)
        if action == "add_access":
            active.add(pair)
        else:
            active.discard(pair)
    while checkpoints:
        write_snapshot(checkpoints.pop(0))

    manifest = {
        "source_url": SOURCE_URL,
        "download_url": DOWNLOAD_URL,
        "citation": "Montanez, K. (2011). Amazon Access Samples. DOI:10.24432/C5JW2K. CC BY 4.0.",
        "source_history_file": "data/raw/amazon_access_history.csv",
        "source_history_sha256": sha256(SOURCE),
        "source_rows_read": read,
        "invalid_rows_skipped": invalid,
        "method": "Sort valid source events by AUTHORIZATION_DATE and original file row number, apply add_access/remove_access events from earliest available record, and emit active observed grants through each year-end cutoff. No records are invented. These are temporal snapshots from one dataset, not five independent datasets. Source timestamps have no stated timezone.",
        "snapshots": snapshots,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshots, indent=2))


if __name__ == "__main__":
    main()