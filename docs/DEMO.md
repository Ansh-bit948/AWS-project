# Demonstration walkthrough

1. Start the local UI or AWS mode using `scripts/Start-Demo.ps1` and sign in with the configured administrator account.
2. Import a CSV from `test_sets/`. Explain its source, dimension counts, and the six explicitly derived graph features using `test_sets/README.md` and `manifest.json`.
3. Open User profiles and Permission catalog. Show grant counts, density, rarity and empirical percentiles computed from the actual matrix.
4. Open Role catalog. Inspect discovered users and permissions and explain the measured structural-cost comparison.
5. Open Risk & review. Review a real rare-grant finding. Approve a revoke only as a benchmark-policy experiment; check authorization changes, then restore it.
6. Open Policy & audit to show version lineage, actor, source hash and actual audit events.
7. In Learning lab, show that feedback Q-learning requires at least five genuine administrator reviews across two users. Do not add simulated labels or claim performance without those records.
8. For AWS mode, demonstrate authenticated API calls, S3-backed input/results, Lambda analysis, DynamoDB policy/audit state, CloudWatch Logs and the configured Budget. The frontend may remain local; free-plan/credit coverage is not a spending cap.

The five sample matrices are static user–permission assignments, not temporal ERP logs. They support structural role mining and review features; they do not support temporal predictions or approval-delay evaluation.
