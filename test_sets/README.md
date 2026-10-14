# Test sets

These five CSVs match the app upload schema (`user_id,permission_id`). They are **year-end snapshots derived from one real enterprise access-history dataset**, not five independent datasets. Only recorded add/remove events are applied; no identities or grants are fabricated.

## Source

- UCI page: https://archive.ics.uci.edu/dataset/216/amazon+access+samples
- Official archive: https://archive.ics.uci.edu/static/public/216/amazon+access+samples.zip
- Citation: Montanez, K. (2011), *Amazon Access Samples*, DOI: 10.24432/C5JW2K, CC BY 4.0.

Events use `AUTHORIZATION_DATE`, `LOGIN`, `TARGET_NAME`, and `ACTION`, ordered by timestamp and original row number. A remove event deletes the pair if present. Cutoffs use the source timestamps; the source does not state a timezone.

| File | Cutoff in source time | Users | Permissions | Grants |
|---|---|---:|---:|---:|
| `amazon_access_snapshot_2006.csv` | 2006-12-31T23:59:59 | 4,212 | 828 | 13,027 |
| `amazon_access_snapshot_2007.csv` | 2007-12-31T23:59:59 | 6,222 | 1,351 | 24,107 |
| `amazon_access_snapshot_2008.csv` | 2008-12-31T23:59:59 | 9,492 | 3,056 | 53,557 |
| `amazon_access_snapshot_2009.csv` | 2009-12-31T23:59:59 | 13,080 | 4,812 | 98,109 |
| `amazon_access_snapshot_2010.csv` | 2010-12-31T23:59:59 | 17,568 | 6,291 | 136,196 |

Exact source/output hashes and the reproducible method are in `manifest.json`. The snapshots support testing role mining and permission analysis. They are historical benchmark states, not current production entitlements or five separate organizations.
