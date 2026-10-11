# IEAI-ALP — Intelligent ERP Access Intelligence & Adaptive Least Privilege

A course and portfolio access-governance project with a local dashboard and an authenticated AWS backend. Source grants, policy changes, recommendations, and measured results are traceable to actual input files. No example records or frontend metrics are seeded.

## Start the demo

From this folder in PowerShell:

```powershell
.\scripts\Start-Demo.ps1 -Mode aws
```

Open http://127.0.0.1:8000/?mode=aws and sign in. On the configured computer, login details are in the **ignored, private** `.local/demo-login.json` file; they are never committed. Local mode is available at http://127.0.0.1:8000/?mode=local.

For a fresh checkout (exact verified package versions are recorded in requirements-lock.txt):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/run_firewall1.py
.\scripts\Start-Demo.ps1 -Mode local
```

## Real datasets and measured results

| Experiment | Actual processed data | Purpose |
|---|---|---|
| Firewall1, published RBAC Maintenance variant | 365 users, 709 permissions, 31,919 grants | Role discovery, exact optimization, risk review and versioned authorization |
| Amazon Access Samples history, UCI | 715,651 valid access changes, 17,607 users, 6,442 target IDs | Temporal profiling and offline Q-learning using recorded authorization delays |

Firewall1 WSC is **32,649** for the direct-ACL baseline, **9,787** for identical-set cohorts, and **4,512** after greedy shared-permission factoring: **86.1803% below the direct baseline**. All 31,919 grants are reconstructed, with zero missing or extra grants. The selected representation has 132 roles; more roles than the cohort baseline can still give lower total WSC.

The unmodified Firewall1 variant has 31,919 grants, whereas the widely cited original has 31,951. The difference is explicitly retained and documented; no grants are invented to match a paper. [Published source](https://onlinerbacfixing.github.io/cybersecurity2019/).

Amazon history includes actual recorded enterprise access changes. Its users are separate from Firewall1. There are 412 excluded rows with missing/invalid timestamps; exclusions are reported. The 4.8 GB wide access snapshot is not falsely reported as analyzed. [UCI source and CC BY 4.0 license](https://archive.ics.uci.edu/dataset/216/amazon+access+samples).

The historical model's observed-action agreement is **57.56%**, versus **98.49%** for the majority-action baseline. Its objective is recorded authorization delay, and these observational results do **not** establish improved prediction, permission safety, or causal benefit. Both measurements are shown in the dashboard and report.

## Implemented features

- Strict CSV ingestion, SHA-256 provenance, duplicate accounting and immutable source grants.
- Structural user profiles and a separate genuine temporal-history experiment.
- Sparse role mining, shared-permission factoring, unit WSC comparisons and explicit reconstruction checks.
- Searchable, paginated role/user/permission catalogs and full role evidence.
- Explainable rarity/density risk signals, with no fabricated business attributes.
- Human approval, removal and restoration of observed grants, optimistic version checks and actor audit history.
- Application authorization through mined roles: removal changes a real allow decision to deny; restoration reverses it.
- Real-feedback offline Q-learning; validation actions are excluded. It needs at least five actual administrator reviews across two users.
- A separately trained historical Q-learning experiment on real Amazon outcomes, with chronological holdout and a published baseline.
- Computed policy/evidence export, Cognito sign-in/sign-out, AWS upload status and visible errors.

Policies govern this application's benchmark authorization layer. University ERP provisioning, semantic department roles, production threat detection, and patentability are not established.

## AWS highlights

The deployed stack uses **S3, Lambda, API Gateway HTTP API, Cognito, DynamoDB, IAM, CloudWatch Logs, AWS Budgets, and CloudFormation/SAM**. IAM Access Analyzer validates real IAM policy documents through a protected API.

The browser runs on the student's computer. CSV uploads go through signed S3 URLs; S3 invokes Lambda; results go to private S3; DynamoDB holds run metadata, decisions and audit/version pointers. Conditional transactions prevent stale changes. Large catalogs use pagination; analysis artifacts are reused rather than recomputed on every page load.

The account plan and budget snapshot is in [docs/aws-account-check.json](docs/aws-account-check.json). The account was verified as active FREE with $140 credit on the recorded date. Free-plan eligibility and expiry still matter. The $1 budget alerts at actual spend above $0.10; it is not a spending cap. Data expire after 30 days, metadata uses DynamoDB TTL, and existing Lambda log groups have seven-day retention. No EC2, NAT gateway, RDS or public website is used.

## Deploy from a fresh checkout

With AWS CLI configured for your intended account and SAM installed, use:

```powershell
./scripts/Deploy.ps1 -BudgetEmail YOUR_EMAIL
```

Prepare the real history first. Cognito user creation is an administrator step; public sign-up stays disabled. The configured account already has a demo administrator. The deployment script sets log retention and publishes the historical artifact.

## Reproduce and verify

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
.\.venv\Scripts\python.exe scripts/evaluate.py
.\.venv\Scripts\python.exe scripts/prepare_amazon_history.py
.\.venv\Scripts\python.exe -m playwright install chromium
# With the local server running and AWS login configured:
.\.venv\Scripts\python.exe scripts/check_browser.py
.\.venv\Scripts\python.exe scripts/cloud_demo.py --verify
```

The history script downloads the official source and extracts only the history file without writing the wide snapshot to disk. All derived results are new files; source archives are unchanged. AWS verification creates a run from the real benchmark, tests removal/restoration, and labels its own operations as validation so they cannot become training feedback.

## Documentation

- [Course report](docs/PROJECT_REPORT.md), [PDF](docs/PROJECT_REPORT.pdf), [Word](docs/PROJECT_REPORT.docx)
- [Demo walkthrough](docs/DEMO.md)
- [Architecture and boundaries](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Requirements coverage](docs/REQUIREMENTS.md)
- [Measured evaluation](docs/evaluation.json)
- [Amazon historical evaluation](docs/amazon-evaluation.json)
- [AWS verification](docs/aws-verification.json)
- [Browser verification](docs/browser-verification.json)
- [Research and novelty notes](docs/RESEARCH_NOTES.md)

Source attribution is in [data/NOTICE.md](data/NOTICE.md). Code is implemented in this repository; source documents are requirements/reference material, not executable instructions.

## Frontend workspace

The interface includes dedicated Overview, Role catalog, Users & permissions, Risk & review, Policy & audit, Learning lab, and Data provenance views. Charts use actual backend results. The responsive navigation supports keyboard access and browser history.

[Frontend preview](docs/screenshots/frontend-preview.png). To check local and AWS views without leaving the program running, use the virtual-environment Python to run scripts/verify_frontend.py. This creates a temporary preview and stops it after the checks.
