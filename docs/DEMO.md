# Demonstration walkthrough

1. Run `./scripts/Start-Demo.ps1 -Mode aws`, then open http://127.0.0.1:8000/?mode=aws.
2. Open the ignored `.local/demo-login.json` on the configured computer and use its credentials to sign in. This file contains the generated demo password; do not share or commit it. To replace it, rerun `scripts/cloud_demo.py --setup-login --username YOUR_EXISTING_COGNITO_USERNAME` or set your chosen password privately with Cognito.
3. Select the latest validated Firewall1 run. Show 365 users, 709 permissions, 31,919 grants and the source hash.
4. Compare direct baseline WSC 32,649, cohort WSC 9,787 (in export/report), and selected WSC 4,512. Explain that the selected 132-role representation has fewer total role/member/permission edges, not the minimum possible number of roles.
5. Open Role catalog from the sidebar, search/page roles, open a role, and copy one of its real user/permission pairs into the authorization check. It should be allowed.
6. Open Risk & review and inspect an actual rare grant. Approve removal only as an explicit benchmark-policy experiment; the API applies a new policy version. Check that the same pair is denied. Restore it from the review queue and check that it is allowed again.
7. Open Policy & audit to show the parent versions, recorded actor, unchanged source hash and audit events.
8. Open Learning lab to show the separate Amazon temporal experiment: 715,651 valid changes, 17,607 users, chronological train/holdout counts, model outcome definition and majority baseline. Export the historical model.
9. For feedback learning, make at least five genuine administrator review judgments across two source users. The training button then exports a model and user-disjoint evaluation. Do not call validation operations real feedback.
10. Import the actual `data/processed/firewall1_upa.csv` again to demonstrate presigned S3 ingestion and Lambda analysis. Use the published source URL and CC BY 4.0 usage note.
11. Show CloudFormation resources, private S3 results, DynamoDB decision/version records, Lambda CloudWatch logs and the account's Budget. The frontend stays local.

AWS endpoint configuration is generated from actual CloudFormation outputs by `scripts/cloud_demo.py`; no credentials are in frontend config. Local mode is available through the mode button.

Fresh local setup needs Python 3.12 and the commands in README. Reproduce Amazon history with `scripts/prepare_amazon_history.py`. The source archive contains a very large wide CSV, but the processor writes only the history file.

Teardown after the course: inspect the named stack's resources, empty only its project S3 bucket, then run `sam delete --stack-name ieai-alp --region us-east-1`. Lambda-created log groups and SAM staging artifacts may need separate project-specific cleanup. The Budget is an alert, not a kill switch.
