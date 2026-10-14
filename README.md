# IEAI-ALP — ERP access intelligence

An AWS-backed access-governance project for inspecting real user–permission assignments, discovering compact roles, reviewing unusual grants, and tracking policy decisions. The benchmark data does not contain university ERP roles or employee attributes, so the application preserves anonymized source identifiers and reports only measured or derived facts.

## Real datasets

`test_sets/` contains five distinct published access matrices from the HP Labs role-mining benchmark family: Americas Small, APJ, Healthcare, Domino, and Firewall2. They are different access systems/domains, not time snapshots. Each CSV has eight columns: the original `user_id` and `permission_id`, plus six deterministic graph features computed from that matrix (assignment counts, density/prevalence, and empirical degree percentiles). The original source files, SHA-256 manifest, exact meanings, benchmark counts, and direct download links are in [test_sets/README.md](test_sets/README.md).

The six extra fields are derived—not source-record metadata. The app verifies them against the assignments and independently recomputes its analytics. Static matrices support role discovery, structural profiling, review signals, and policy-structure optimization. They do not support time-based behavior or approval-delay predictions. Feedback Q-learning remains disabled until the app has at least five genuine human reviews across two users; no simulated feedback is included.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Import one of the CSVs from `test_sets/` via the dataset upload flow. The five files are under the current importer’s 25 MiB limit. To reproduce the enriched CSVs from the retained source matrices, run:

```powershell
.\.venv\Scripts\python.exe scripts/build_test_sets.py
```

## AWS architecture

The SAM/CloudFormation stack configures API Gateway, Lambda, Cognito, private S3, DynamoDB, IAM, CloudWatch Logs, and AWS Budgets. S3 stores source files and computed artifacts; Lambda performs analysis and serves APIs; Cognito authenticates the administrator; DynamoDB stores dataset metadata, policy versions, decisions and audit events. Access Analyzer validates IAM identity policies. The browser can remain local while invoking the AWS backend.

Deploy only when needed with a configured AWS CLI/SAM installation:

```powershell
./scripts/Deploy.ps1 -BudgetEmail YOUR_EMAIL
```

AWS Free Tier/credits are account- and date-dependent. A budget only sends alerts; it does not cap spending. No services are deployed by running the application locally.

## Project boundaries

The app uses actual uploaded grants, builds explainable profiles, mines roles, checks exact reconstruction, compares unit policy cost, and applies reversible approval-backed policy changes. It does not provision a real ERP, use live corporate IAM, or establish that any learned role is operationally safe. RL requires actual administrator feedback and abstains without enough evidence. Patentability is not established.

See [course report](docs/PROJECT_REPORT.md), [dataset provenance](test_sets/README.md), [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [demo guide](docs/DEMO.md), [requirements coverage](docs/REQUIREMENTS.md), and [research notes](docs/RESEARCH_NOTES.md).
