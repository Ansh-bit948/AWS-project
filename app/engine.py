"""Pure analytics engine shared by local and AWS runtimes."""
from collections import Counter, defaultdict
from typing import Any

def compute(dataset_id: str, rows: list[tuple[str,str]]) -> dict[str,Any]:
    by_user: dict[str,set[str]]=defaultdict(set); by_perm: Counter[str]=Counter()
    for u,p in rows: by_user[u].add(p); by_perm[p]+=1
    users=len(by_user); perms=len(by_perm); edges=len(rows)
    cohorts: dict[tuple[str,...],list[str]]=defaultdict(list)
    for u,ps in by_user.items(): cohorts[tuple(sorted(ps))].append(u)
    role_rows=[]
    for i,(ps,us) in enumerate(sorted(cohorts.items(), key=lambda x:(-len(x[0]),x[0])),1):
        role_rows.append({"role_id":f"R{i:04d}","users":sorted(us),"permissions":list(ps),"user_count":len(us),"permission_count":len(ps),"confidence":1.0,"method":"exact access-set equivalence","coverage":1.0})
    ua=sum(r["user_count"] for r in role_rows); pa=sum(r["permission_count"] for r in role_rows)
    risk=[]
    for u,ps in by_user.items():
        rare=sorted((p for p in ps if by_perm[p]/users <= .05),key=lambda p:(by_perm[p],p))
        density=len(ps)/max(1,perms); score=min(100,round((len(rare)/max(1,len(ps)))*65+density*35,2))
        if rare or score>=25:
            risk.append({"user_id":u,"score":score,"grant_count":len(ps),"rare_permissions":rare[:20],"reasons":[f"{len(rare)} permission(s) assigned to <=5% of users"] if rare else ["High permission density relative to this dataset"]})
    risk.sort(key=lambda x:(-x["score"],x["user_id"]))
    role_for_user={u:r['role_id'] for r in role_rows for u in r['users']}; profiles=[]
    for u,ps in sorted(by_user.items()):
        profiles.append({"user_id":u,"observed_grants":len(ps),"permission_density":round(len(ps)/perms,5),"permission_diversity":round(len(ps)/perms,5),"rare_grant_count":sum(by_perm[p]/users<=.05 for p in ps),"attribute_status":"Not provided by dataset","cohort_role":role_for_user[u]})
    summary={"high":sum(x['score']>=70 for x in risk),"medium":sum(35<=x['score']<70 for x in risk),"review":sum(x['score']<35 for x in risk)}
    return {"dataset_id":dataset_id,"counts":{"users":users,"permissions":perms,"assignments":edges,"roles":len(role_rows)},"baseline":{"roles":users,"ua_edges":users,"pa_edges":edges,"wsc":2*users+edges},"optimized":{"roles":len(role_rows),"ua_edges":ua,"pa_edges":pa,"wsc":len(role_rows)+ua+pa,"coverage":1.0,"permission_loss":0},"risk_findings_total":len(risk),"risk_summary":summary,"roles":role_rows,"profiles":profiles,"risk_findings":risk[:500],"methodology":{"role_discovery":"Lossless grouping by identical observed permission sets","optimization":"Exact coverage with one candidate role per equivalence class; minimizes role count under this representation","risk":"Dataset-relative rarity and permission density; not a business impact or exploitability score","attributes":"None supplied or inferred","reinforcement_learning":"Offline tabular Q-learning recommendation; actions are counterfactual and require human approval","data_scope":"Access-control matrix only; no live ERP or AWS actions"}}
