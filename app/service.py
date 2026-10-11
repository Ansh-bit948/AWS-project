"""Shared API business rules for FastAPI and authenticated Lambda."""
from .engine import compute
from .governance import authorize, feedback_state, recommendations, train_feedback
from .local_store import Conflict

def page(rows, query):
    offset = max(0, int(query.get('offset',0)))
    limit = max(1,min(100,int(query.get('limit',25))))
    search = query.get('search','').lower()
    if search:
        rows = [r for r in rows if search in str(r.get('user_id',r.get('permission_id',r.get('role_id','')))).lower()]
    return {'items':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit}

def compact(a):
    return a | {'roles':[ {k:v for k,v in r.items() if k not in ('users','permissions')} for r in a['roles'][:100]],
                'profiles':a['profiles'][:50], 'risk_findings':a['risk_findings'][:25], 'permission_catalog':a.get('permission_catalog',[])[:50]}

def dispatch(method, path, query, body, store, actor):
    parts = path.strip('/').split('/')
    if parts[0] == 'catalog' and len(parts) != 3:
        return 404, {'error':'Route not found'}
    if parts[0] == 'rl' and (len(parts) != 3 or parts[1] != 'train'):
        return 404, {'error':'Route not found'}
    try:
        if method == 'GET' and parts == ['datasets']:
            return 200, {'datasets':store.datasets()}
        if len(parts) > 1 and parts[0] in ('analytics','recommendations','policy-versions','audit','catalog','authorize','rl','export'):
            did = parts[-1] if parts[0] != 'catalog' else parts[2]
        elif parts[0] == 'decisions':
            did = body.get('dataset_id')
        else:
            return 404, {'error':'Route not found'}
        if not isinstance(did,str) or not did:
            return 400, {'error':'dataset_id is required'}
        meta,a = store.get(did)
        if method == 'GET' and parts[0] == 'analytics':
            return 200, {'dataset':meta,'analysis':compact(a) if query.get('compact') == '1' else a}
        if method == 'GET' and parts[0] == 'recommendations':
            rec = recommendations(a,store.decisions(did))
            return 200, {'dataset_id':did,**page(rec['recommendations'],query),'note':rec['note']}
        if method == 'GET' and parts[0] == 'policy-versions':
            return 200, page(store.history(did),query)
        if method == 'GET' and parts[0] == 'audit':
            return 200, page(store.audit(did),query)
        if method == 'GET' and parts[0] == 'catalog' and parts[1] in ('roles','profiles','permission_catalog'):
            rows = a[parts[1]]
            if query.get('id'):
                row = next((r for r in rows if r.get('role_id',r.get('user_id',r.get('permission_id'))) == query['id']),None)
                return (200,row) if row else (404,{'error':'Catalog item not found'})
            return 200,page(rows,query)
        if method == 'GET' and parts[0] == 'export':
            return 200, {'dataset':meta,'analysis':a,'decisions':store.decisions(did),'policy_versions':store.history(did),
                         'export_scope':'Application RBAC grant labels; never an AWS IAM action mapping'}
        if method == 'POST' and parts[0] == 'authorize':
            if not body.get('user_id') or not body.get('permission_id'):
                raise ValueError('user_id and permission_id are required')
            return 200,authorize(a,body['user_id'],body['permission_id'])
        if method == 'POST' and parts[0] == 'decisions':
            u,p,d = body.get('user_id'),body.get('permission_id'),body.get('decision')
            if not all(isinstance(x,str) and x for x in (u,p)) or d not in ('revoke','retain'):
                raise ValueError('user_id, permission_id, and decision (revoke or retain) are required')
            expected = int(body.get('expected_version',-1))
            if expected != int(a.get('policy_version',1)):
                raise Conflict('Policy changed. Reload and review the latest version.')
            source = store.source_pairs(did)
            if (u,p) not in set(source):
                return 404, {'error':'Grant is not present in the immutable source dataset'}
            old = next((x for x in store.decisions(did) if x['user_id']==u and x['permission_id']==p),None)
            changed = (bool(old and old['decision']=='revoke') != (d=='revoke'))
            removed = {(x['user_id'],x['permission_id']) for x in store.decisions(did) if x['decision']=='revoke'}
            if d == 'revoke':
                removed.add((u,p))
            else:
                removed.discard((u,p))
            result = compute(did,[x for x in source if x not in removed],sorted({u for u,p in source}),sorted({p for u,p in source})) if changed else a
            result['policy_version'] = expected + int(changed)
            if 'quality' in a:
                result['quality'] = a['quality']
            profile = next(x for x in a['profiles'] if x['user_id']==u)
            purpose = body.get('purpose','review')
            if purpose not in ('review','validation'):
                raise ValueError('purpose must be review or validation')
            decision = {'user_id':u,'permission_id':p,'decision':d,'purpose':purpose,'state':feedback_state(profile)}
            store.commit(did,expected,decision,result,changed,actor)
            return 200, {'status':'recorded','decision':d,'policy_version':result['policy_version'],
                         'active_policy_updated':changed,'source_dataset_unchanged':True}
        if method == 'POST' and parts[:2] == ['rl','train']:
            report = train_feedback(a,store.audit(did),body.get('episodes',500))
            return 200,store.save_model(did,report,actor)
        return 404, {'error':'Route not found'}
    except KeyError as e:
        return 404, {'error':str(e)}
    except Conflict as e:
        return 409, {'error':str(e)}
    except (ValueError,TypeError) as e:
        return 400, {'error':str(e)}
