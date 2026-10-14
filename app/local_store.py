"""SQLite persistence with immutable source analysis and versioned effective policies."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .engine import compute

def stamp():
    return datetime.now(timezone.utc).isoformat()

class Conflict(Exception):
    pass

class LocalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY,name TEXT,source_url TEXT,sha256 TEXT,uploaded_at TEXT,users INTEGER,permissions INTEGER,edges INTEGER,run_id TEXT,license_note TEXT DEFAULT '',policy_version INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS grants(dataset_id TEXT,user_id TEXT,permission_id TEXT,PRIMARY KEY(dataset_id,user_id,permission_id),FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,dataset_id TEXT,created_at TEXT,result TEXT);
            CREATE TABLE IF NOT EXISTS decisions(dataset_id TEXT,user_id TEXT,permission_id TEXT,decision TEXT,version INTEGER,created_at TEXT,PRIMARY KEY(dataset_id,user_id,permission_id));
            CREATE TABLE IF NOT EXISTS policy_versions(dataset_id TEXT,version INTEGER,parent_version INTEGER,change_summary TEXT,actor TEXT,created_at TEXT,PRIMARY KEY(dataset_id,version));
            CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,dataset_id TEXT,actor TEXT,action TEXT,details TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS policy_artifacts(dataset_id TEXT,version INTEGER,result TEXT,PRIMARY KEY(dataset_id,version));
            CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY,dataset_id TEXT,created_at TEXT,result TEXT);
            """)
            c.execute("PRAGMA journal_mode=WAL")
    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            with c:
                yield c
        finally:
            c.close()
    def datasets(self):
        with self.db() as c:
            return [dict(r) | {'dataset_id': r['id'], 'status': 'ready'} for r in c.execute('SELECT * FROM datasets ORDER BY uploaded_at DESC')]
    def import_data(self, pairs, meta, quality, actor='local-admin'):
        did, rid, ts = str(uuid.uuid4()), str(uuid.uuid4()), stamp()
        source_context = quality.pop('source_context', None)
        result = compute(did, pairs, source_context=source_context)
        result.update(policy_version=1, quality=quality)
        with self.db() as c:
            c.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (did,meta['name'],meta['source_url'],quality['sha256'],ts,result['counts']['users'],result['counts']['permissions'],len(pairs),rid,meta['license_note'],1))
            c.executemany('INSERT INTO grants VALUES(?,?,?)',[(did,u,p) for u,p in pairs])
            c.execute('INSERT INTO runs VALUES(?,?,?,?)',(rid,did,ts,json.dumps(result)))
            c.execute('INSERT INTO policy_artifacts VALUES(?,?,?)',(did,1,json.dumps(result)))
            c.execute('INSERT INTO policy_versions VALUES(?,?,?,?,?,?)',(did,1,None,'Imported immutable source grants',actor,ts))
            self._audit(c,did,actor,'dataset_import',quality)
        return {'dataset_id': did, 'run_id': rid, 'counts': result['counts'], 'sha256': quality['sha256'], 'quality': quality}
    def get(self, did):
        with self.db() as c:
            d = c.execute('SELECT * FROM datasets WHERE id=?',(did,)).fetchone()
            if not d:
                raise KeyError('Dataset not found')
            meta = dict(d) | {'dataset_id': did, 'status': 'ready'}
            cached = c.execute('SELECT result FROM policy_artifacts WHERE dataset_id=? AND version=?',(did,d['policy_version'])).fetchone()
            if cached:
                return meta, json.loads(cached['result'])
            # Upgrade existing local databases without losing the immutable grant matrix.
            source = [(r['user_id'],r['permission_id']) for r in c.execute('SELECT * FROM grants WHERE dataset_id=?',(did,))]
            removed = {(r['user_id'],r['permission_id']) for r in c.execute("SELECT * FROM decisions WHERE dataset_id=? AND decision='revoke'",(did,))}
            a = compute(did,[p for p in source if p not in removed],sorted({u for u,p in source}),sorted({p for u,p in source}))
            a['policy_version'] = int(d['policy_version'])
            c.execute('INSERT INTO policy_artifacts VALUES(?,?,?)',(did,d['policy_version'],json.dumps(a)))
            return meta,a
    def source_pairs(self, did):
        with self.db() as c:
            return [(r['user_id'],r['permission_id']) for r in c.execute('SELECT * FROM grants WHERE dataset_id=?',(did,))]
    def decisions(self, did):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM decisions WHERE dataset_id=?',(did,))]
    def history(self, did):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM policy_versions WHERE dataset_id=? ORDER BY version DESC',(did,))]
    def audit(self, did):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM audit WHERE dataset_id=? ORDER BY created_at DESC',(did,))]
    def _audit(self,c,did,actor,action,details):
        c.execute('INSERT INTO audit VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),did,actor,action,json.dumps(details),stamp()))
    def commit(self, did, expected, decision, analysis, changed, actor):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            d = c.execute('SELECT policy_version FROM datasets WHERE id=?',(did,)).fetchone()
            if not d or d['policy_version'] != expected:
                raise Conflict('Policy changed. Reload and review the latest version.')
            version, ts = expected + int(changed), stamp()
            c.execute('INSERT OR REPLACE INTO decisions VALUES(?,?,?,?,?,?)',
                      (did,decision['user_id'],decision['permission_id'],decision['decision'],version,ts))
            if changed:
                c.execute('UPDATE datasets SET policy_version=? WHERE id=?',(version,did))
                c.execute('INSERT INTO policy_artifacts VALUES(?,?,?)',(did,version,json.dumps(analysis)))
                c.execute('INSERT INTO policy_versions VALUES(?,?,?,?,?,?)',
                          (did,version,expected,json.dumps(decision),actor,ts))
            self._audit(c,did,actor,'permission_decision',decision | {'policy_version': version})
    def save_model(self,did,report,actor):
        mid,ts = str(uuid.uuid4()),stamp()
        report['model_id'] = mid
        with self.db() as c:
            c.execute('INSERT INTO models VALUES(?,?,?,?)',(mid,did,ts,json.dumps(report)))
            self._audit(c,did,actor,'feedback_rl_run',{'model_id':mid,'feedback_sha256':report['feedback_sha256']})
        return report
