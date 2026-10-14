# API reference

Local prefix: `/api`. AWS routes have the same paths without that prefix and require a Cognito ID JWT in `Authorization: Bearer TOKEN`.

| Method and path | Behavior |
|---|---|
| GET /datasets | Actual datasets, source metadata and import status |
| POST /datasets/import | Local multipart CSV; file, name, source_url, license_note |
| POST /datasets/presign | AWS JSON filename/name/source_url/license_note; returns signed URL and exact upload headers |
| GET /analytics/{dataset_id}?compact=1 | Computed active-policy analytics and immutable-source metadata |
| GET /catalog/{roles,profiles,permission_catalog}/{dataset_id} | Search and pagination; query offset, limit (max 100), search |
| GET /catalog/roles/{dataset_id}?id=ROLE_ID | Full actual role members and permissions |
| GET /recommendations/{dataset_id} | Evidence-based review queue; offset/limit |
| POST /decisions | JSON dataset_id, user_id, permission_id, decision, expected_version |
| GET /policy-versions/{dataset_id} | Versions, parent version and actor; offset/limit |
| GET /audit/{dataset_id} | Actual audit events; offset/limit |
| POST /authorize/{dataset_id} | JSON user_id/permission_id; allowed and matching roles |
| POST /rl/train/{dataset_id} | JSON episodes (1-10,000); train and persist a real-feedback model |
| GET /export/{dataset_id} | Current policy, decisions, source metadata and versions |
| POST /security/validate | AWS only; actual IAM policy_document; Access Analyzer findings |
| GET /health | Local only; service state |

Decision `revoke` removes a source grant from effective policy. Decision `retain` keeps/restores it. `expected_version` is mandatory. A stale version returns 409. Validation tooling sends `purpose: validation`; such events are excluded from model training. Normal administrator UI decisions are recorded as genuine reviews.

A missing dataset returns 404; invalid data/insufficient genuine feedback returns 400; missing authentication returns 401. The full AWS response is capped below Lambda's synchronous payload limit. Use compact analytics and catalog pagination for large datasets.

\n