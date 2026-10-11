"""Verification uses the attributed Firewall1 source, never seeded demo records."""
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.engine import compute
from app.ingestion import parse_csv
from app.local_store import LocalStore
from app.governance import train_feedback

ROOT=Path(__file__).resolve().parents[1]
RAW=(ROOT/'data/processed/firewall1_upa.csv').read_bytes()

@pytest.fixture(scope='module')
def rows():
    return parse_csv(RAW)[0]

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'store',LocalStore(tmp_path/'isolated.sqlite3'))
    with TestClient(main.app) as c:
        yield c

def upload(client):
    r=client.post('/api/datasets/import',files={'file':('firewall1.csv',RAW,'text/csv')},
                  data={'name':'Firewall1 published benchmark','source_url':'https://onlinerbacfixing.github.io/cybersecurity2019/','license_note':'CC BY 4.0'})
    assert r.status_code==200,r.text
    return r.json()['dataset_id']

def test_source_hash_and_counts(rows):
    assert hashlib.sha256(RAW).hexdigest()=='cf5434adbbb891ba1ae4c9fb172510b81030d28b91ee4aebac95d64524426c91'
    assert len(rows)==31919
    assert len({u for u,p in rows})==365
    assert len({p for u,p in rows})==709

def test_role_reconstruction_and_wsc(rows):
    a=compute('source-check',rows)
    reconstructed={(u,p) for r in a['roles'] for u in r['users'] for p in r['permissions']}
    assert reconstructed==set(rows)
    assert a['optimized']['wsc']<=a['cohort_baseline']['wsc']<=a['baseline']['wsc']
    assert a['optimized']['overgrants']==a['optimized']['permission_loss']==0
    assert a['optimized']['wsc']==sum(1+len(r['users'])+len(r['permissions']) for r in a['roles'])

def test_duplicate_counts_and_determinism(rows):
    first=compute('same',rows)
    second=compute('same',list(reversed(rows))+rows[:10])
    first.pop('performance');second.pop('performance')
    assert first==second

def test_zero_grant_subjects_preserved(rows):
    users=sorted({u for u,p in rows});perms=sorted({p for u,p in rows})
    user=users[0]
    a=compute('removal',[r for r in rows if r[0]!=user],users,perms)
    assert a['counts']['users']==365
    assert next(p for p in a['profiles'] if p['user_id']==user)['observed_grants']==0

def test_metadata_pagination_and_catalog(client):
    did=upload(client)
    d=client.get('/api/datasets').json()['datasets'][0]
    assert d['name']=='Firewall1 published benchmark'
    assert d['source_url'].startswith('https://')
    for kind in ['roles','profiles','permission_catalog']:
        page=client.get(f'/api/catalog/{kind}/{did}?offset=25&limit=25').json()
        assert len(page['items'])==25 and page['total']>=50
    detail=client.get(f'/api/catalog/roles/{did}?id=R0001').json()
    assert detail['users'] and detail['permissions']

def test_revoke_restore_concurrency_source_integrity(client,rows):
    did=upload(client);u,p=rows[0]
    def check():
        return client.post(f'/api/authorize/{did}',json={'user_id':u,'permission_id':p}).json()['allowed']
    assert check()
    body={'dataset_id':did,'user_id':u,'permission_id':p,'decision':'revoke','expected_version':1,'purpose':'validation'}
    r=client.post('/api/decisions',json=body)
    assert r.status_code==200 and r.json()['policy_version']==2
    assert not check()
    assert client.post('/api/decisions',json=body).status_code==409
    rec=client.get(f'/api/recommendations/{did}?limit=100').json()
    assert any(x['status']=='revoke' and x['user_id']==u and x['permission_id']==p for x in rec['items'])
    body.update(decision='retain',expected_version=2)
    assert client.post('/api/decisions',json=body).json()['policy_version']==3
    assert check()
    export=client.get(f'/api/export/{did}').json()
    assert export['dataset']['sha256']==hashlib.sha256(RAW).hexdigest()
    assert export['analysis']['counts']['assignments']==31919
    assert len(export['policy_versions'])==3
    assert client.post(f'/api/rl/train/{did}',json={}).status_code==400
    assert len(client.get(f'/api/audit/{did}').json()['items'])==3

def test_empty_mode_and_validation(client,rows):
    assert client.get('/api/datasets').json()=={'datasets':[]}
    assert client.get('/api/analytics/absent').status_code==404
    assert client.post('/api/datasets/import',files={'file':('invalid.csv',b'user_id,permission_id\n','text/csv')}).status_code==400
    assert client.post('/api/datasets/import',files={'file':('invalid.csv',b'wrong,header\n','text/csv')}).status_code==400
    assert client.post('/api/decisions',content='not json').status_code==400
    assert client.post('/api/decisions',json={},headers={'origin':'https://untrusted.example'}).status_code==403

def test_no_simulated_learning(rows):
    with pytest.raises(ValueError,match='genuine administrator'):
        train_feedback(compute('real-source',rows),[],500)

def test_compact_keeps_measured_counts(client):
    did=upload(client)
    payload=client.get(f'/api/analytics/{did}?compact=1').json()
    assert payload['analysis']['counts']['assignments']==31919
    assert len(payload['analysis']['profiles'])==50
    assert 'users' not in payload['analysis']['roles'][0]
