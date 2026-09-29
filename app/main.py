"""IEAI-ALP API. All displayed analytics are computed from imported source rows."""
from __future__ import annotations

import csv, hashlib, io, json, os, sqlite3, uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .engine import compute

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("IEAI_DB", ROOT / "data" / "ieai.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="IEAI-ALP", version="0.1.0", description="Evidence-backed access intelligence; no seeded example data")

def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db() -> None:
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY,name TEXT,source_url TEXT,sha256 TEXT,uploaded_at TEXT,users INTEGER,permissions INTEGER,edges INTEGER,run_id TEXT,license_note TEXT DEFAULT '',policy_version INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS grants(dataset_id TEXT,user_id TEXT,permission_id TEXT,PRIMARY KEY(dataset_id,user_id,permission_id),FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,dataset_id TEXT,created_at TEXT,result TEXT,FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,dataset_id TEXT,state TEXT,action TEXT,reward REAL,created_at TEXT,FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,dataset_id TEXT,actor TEXT,action TEXT,details TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS decisions(dataset_id TEXT,user_id TEXT,permission_id TEXT,decision TEXT,version INTEGER,created_at TEXT,PRIMARY KEY(dataset_id,user_id,permission_id),FOREIGN KEY(dataset_id) REFERENCES datasets(id));
        CREATE TABLE IF NOT EXISTS policy_versions(dataset_id TEXT,version INTEGER,parent_version INTEGER,change_summary TEXT,actor TEXT,created_at TEXT,PRIMARY KEY(dataset_id,version),FOREIGN KEY(dataset_id) REFERENCES datasets(id));
        """)
        if "license_note" not in {r[1] for r in c.execute("PRAGMA table_info(datasets)")}:
            c.execute("ALTER TABLE datasets ADD COLUMN license_note TEXT DEFAULT ''")
        if "policy_version" not in {r[1] for r in c.execute("PRAGMA table_info(datasets)")}:
            c.execute("ALTER TABLE datasets ADD COLUMN policy_version INTEGER DEFAULT 1")

init_db()

def now() -> str: return datetime.now(timezone.utc).isoformat()

def latest_dataset(c: sqlite3.Connection):
    row = c.execute("SELECT * FROM datasets ORDER BY uploaded_at DESC LIMIT 1").fetchone()
    if not row: raise HTTPException(404, "No dataset imported. Import a licensed source UPA CSV to compute results.")
    return row

@app.get("/api/health")
def health(): return {"status":"ok","service":"ieai-alp","data_loaded":bool(db().execute("SELECT 1 FROM datasets LIMIT 1").fetchone())}

@app.get("/api/datasets")
def datasets():
    with db() as c: return [dict(r) for r in c.execute("SELECT id,name,source_url,sha256,uploaded_at,users,permissions,edges,run_id,license_note FROM datasets ORDER BY uploaded_at DESC")]

@app.post("/api/datasets/import")
async def import_csv(file: UploadFile=File(...), name: str="", source_url: str="", license_note: str=""):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a CSV with user_id,permission_id columns")
    raw=await file.read()
    if len(raw)>100*1024*1024: raise HTTPException(413,"CSV exceeds 100 MiB upload limit; use the offline importer for larger files")
    digest=hashlib.sha256(raw).hexdigest()
    try:
        reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames: raise ValueError("CSV is empty")
        names={x.strip().lower():x for x in reader.fieldnames}
        uc=next((names[k] for k in ("user_id","user","uid") if k in names),None)
        pc=next((names[k] for k in ("permission_id","permission","resource_id","rid") if k in names),None)
        if not uc or not pc: raise ValueError("Required columns: user_id and permission_id (accepted aliases: user/uid, permission/resource_id/rid)")
        pairs=set()
        for row in reader:
            u=(row.get(uc) or "").strip(); p=(row.get(pc) or "").strip()
            if not u or not p: raise ValueError("Blank user or permission found; correct source rows rather than silently dropping them")
            pairs.add((u,p))
        if not pairs: raise ValueError("No assignment rows found")
    except (UnicodeDecodeError,csv.Error,ValueError) as e: raise HTTPException(400,str(e))
    did=str(uuid.uuid4()); rid=str(uuid.uuid4()); stamp=now(); result=compute(did,list(pairs))
    with db() as c:
        c.execute("INSERT INTO datasets(id,name,source_url,sha256,uploaded_at,users,permissions,edges,run_id,license_note,policy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(did,name or file.filename,source_url or "User supplied; source not asserted",digest,stamp,result['counts']['users'],result['counts']['permissions'],result['counts']['assignments'],rid,license_note,1))
        c.executemany("INSERT INTO grants VALUES(?,?,?)",[(did,u,p) for u,p in sorted(pairs)])
        c.execute("INSERT INTO runs VALUES(?,?,?,?)",(rid,did,stamp,json.dumps(result)))
        c.execute("INSERT INTO policy_versions VALUES(?,?,?,?,?,?)",(did,1,None,"Imported baseline access matrix", "local-admin",stamp))
        c.execute("INSERT INTO audit VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),did,"local-admin","dataset_import",json.dumps({"sha256":digest,"unique_assignments":len(pairs)}),stamp))
    return {"dataset_id":did,"run_id":rid,"sha256":digest,"message":"Imported and analyzed source rows; exact duplicates counted once.","counts":result['counts']}

@app.get("/api/analytics")
def analytics(dataset_id: str|None=None):
    with db() as c:
        d=c.execute("SELECT * FROM datasets WHERE id=?",(dataset_id,)).fetchone() if dataset_id else latest_dataset(c)
        if not d: raise HTTPException(404,"Dataset not found")
        r=c.execute("SELECT result FROM runs WHERE id=?",(d['run_id'],)).fetchone()
        removed={(x['user_id'],x['permission_id']) for x in c.execute("SELECT user_id,permission_id FROM decisions WHERE dataset_id=? AND decision='revoke'",(d['id'],))}
        rows=[(x['user_id'],x['permission_id']) for x in c.execute("SELECT user_id,permission_id FROM grants WHERE dataset_id=?",(d['id'],)) if (x['user_id'],x['permission_id']) not in removed]
        result=compute(d['id'],rows); result['policy_version']=d['policy_version']
        return {"dataset":dict(d),"analysis":result}

@app.get("/api/recommendations")
def recommendations(dataset_id: str|None=None):
    payload=analytics(dataset_id); a=payload['analysis']
    actions=[]
    with db() as c:
        decisions={(x['user_id'],x['permission_id']):x['decision'] for x in c.execute("SELECT user_id,permission_id,decision FROM decisions WHERE dataset_id=?",(a['dataset_id'],))}
    for f in a['risk_findings'][:100]:
        for permission in f['rare_permissions']:
            decision=decisions.get((f['user_id'],permission))
            actions.append({"id":f"review:{f['user_id']}:{permission}","user_id":f['user_id'],"permission_id":permission,"action":"review_rare_grant","target":f['user_id'],"evidence":[permission],"expected_effect":"Remove this grant from the application's active policy snapshot after human approval","confidence":min(.99,.5+1/max(1,f['grant_count'])*.49),"status":decision or "pending_review","automated_change":False})
    return {"dataset_id":a['dataset_id'],"recommendations":actions,"note":"Recommendations are derived from observed matrix rarity; no permission is changed automatically."}

@app.post("/api/decisions")
def decide(payload: dict[str,Any]):
    did=payload.get('dataset_id'); user=payload.get('user_id'); perm=payload.get('permission_id'); decision=payload.get('decision')
    if decision not in ('revoke','retain'): raise HTTPException(400,"decision must be revoke or retain")
    if not all(isinstance(x,str) and x for x in (did,user,perm)): raise HTTPException(400,"dataset_id, user_id, and permission_id are required")
    with db() as c:
        d=c.execute("SELECT policy_version FROM datasets WHERE id=?",(did,)).fetchone()
        if not d: raise HTTPException(404,"Dataset not found")
        if not c.execute("SELECT 1 FROM grants WHERE dataset_id=? AND user_id=? AND permission_id=?",(did,user,perm)).fetchone(): raise HTTPException(404,"Grant is not present in the original dataset")
        previous=c.execute("SELECT decision FROM decisions WHERE dataset_id=? AND user_id=? AND permission_id=?",(did,user,perm)).fetchone()
        old_active=bool(previous and previous['decision']=='revoke'); new_active=decision=='revoke'
        version=d['policy_version']+(1 if old_active!=new_active else 0)
        c.execute("INSERT OR REPLACE INTO decisions VALUES(?,?,?,?,?,?)",(did,user,perm,decision,version,now()))
        if old_active!=new_active:
            c.execute("UPDATE datasets SET policy_version=? WHERE id=?",(version,did))
            action="Revoke" if new_active else "Restore"
            c.execute("INSERT INTO policy_versions VALUES(?,?,?,?,?,?)",(did,version,d['policy_version'],f"{action} observed grant {user} → {perm}","local-admin",now()))
        details=json.dumps({"user_id":user,"permission_id":perm,"decision":decision,"policy_version":version})
        c.execute("INSERT INTO audit VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),did,"local-admin","permission_decision",details,now()))
    return {"status":"recorded","decision":decision,"policy_version":version,"active_policy_updated":old_active!=new_active,"source_dataset_unchanged":True}

@app.get("/api/policy-versions")
def policy_versions(dataset_id: str|None=None):
    with db() as c:
        d=c.execute("SELECT id FROM datasets WHERE id=?",(dataset_id,)).fetchone() if dataset_id else latest_dataset(c)
        if not d: raise HTTPException(404,"Dataset not found")
        return [dict(x) for x in c.execute("SELECT * FROM policy_versions WHERE dataset_id=? ORDER BY version DESC",(d['id'],))]

@app.post("/api/rl/train")
def train_rl(dataset_id: str|None=None, episodes: int=500):
    payload=analytics(dataset_id); a=payload['analysis']; episodes=max(1,min(episodes,10000)); did=a['dataset_id']
    # Deterministic, data-backed one-step offline Q-learning. Rewards derive from measured risk findings.
    q=defaultdict(lambda:[0.0,0.0,0.0]); counts=Counter(); rare_by_user={x['user_id']:len(x['rare_permissions']) for x in a['risk_findings']}
    prof=a['profiles']; states=[(p['user_id'],min(4,p['rare_grant_count'])) for p in prof]
    if not states: raise HTTPException(400,"Dataset has no profiles")
    import random
    rng=random.Random(73); alpha=.15; gamma=.0; epsilon=.15
    # Counterfactual action values: retain, propose review, propose removal; never mutate access.
    for _ in range(episodes):
        uid,state=rng.choice(states); action=rng.randrange(3); rare=rare_by_user.get(uid,0)
        reward={0:0.0,1:(0.5 if rare else -0.1),2:(0.8 if rare else -1.0)}[action]
        q[(state,action)][action]+=alpha*(reward-q[(state,action)][action]); counts[action]+=1
    policy=[]
    for uid,state in states:
        values=[q[(state,i)][i] for i in range(3)]; act=max(range(3),key=lambda i:values[i])
        policy.append({"user_id":uid,"state_rare_grant_bucket":state,"recommendation":["retain","review","propose_revoke"][act],"q_value":round(values[act],4),"approval_required":True})
    report={"episodes":episodes,"state_definition":"min(rare grants assigned to user, 4); rarity threshold <=5% of dataset users","actions":["retain","review","propose_revoke"],"reward":"counterfactual heuristic from observed permission rarity; not real approval outcomes","action_counts":dict(counts),"recommendations":policy,"evaluation":"No held-out real administrator feedback available; Q-values are research output, not validated policy.","model":"tabular Q-learning, seeded for reproducibility; learning signal explicitly counterfactual"}
    with db() as c: c.execute("INSERT INTO audit VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),did,"local-admin","offline_rl_run",json.dumps({"episodes":episodes,"model":"tabular-q-v1"}),now()))
    return report

@app.get("/api/policy/{role_id}")
def policy(role_id: str,dataset_id: str|None=None):
    a=analytics(dataset_id)['analysis']; role=next((r for r in a['roles'] if r['role_id']==role_id),None)
    if not role: raise HTTPException(404,"Role not found")
    # AWS policy is illustrative mapping of dataset permission IDs, not a deployable IAM authorization.
    return {"role":role,"aws_iam_policy":{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":role['permissions'],"Resource":"*"}]},"warning":"Permission identifiers are dataset-specific labels, not verified AWS actions/resources. This JSON is an export artifact only and must not be attached to an IAM principal."}

@app.get("/api/audit")
def audit(dataset_id: str|None=None):
    with db() as c:
        d=c.execute("SELECT id FROM datasets WHERE id=?",(dataset_id,)).fetchone() if dataset_id else latest_dataset(c)
        if not d: raise HTTPException(404,"Dataset not found")
        return [dict(x) for x in c.execute("SELECT * FROM audit WHERE dataset_id=? ORDER BY created_at DESC",(d['id'],))]

app.mount("/static",StaticFiles(directory=ROOT/"app"/"static"),name="static")
@app.get("/")
def home(): return FileResponse(ROOT/"app"/"static"/"index.html")
