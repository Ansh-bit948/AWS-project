"""Reproduce integrity and performance results using the published benchmark."""
import hashlib
import json
import platform
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.engine import compute, ENGINE_VERSION
from app.ingestion import parse_csv

def main():
    raw=(ROOT/'data/processed/firewall1_upa.csv').read_bytes()
    rows,quality=parse_csv(raw)
    # Warm run before timing; every run uses the unchanged real source.
    compute('evaluation',rows)
    timings=[]
    for _ in range(7):
        started=time.perf_counter()
        result=compute('evaluation',rows)
        timings.append((time.perf_counter()-started)*1000)
    tracemalloc.start()
    compute('memory-evaluation',rows)
    peak=tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    rebuilt={(u,p) for r in result['roles'] for u in r['users'] for p in r['permissions']}
    assert rebuilt==set(rows)
    report={'measured_at_utc':datetime.now(timezone.utc).isoformat(),'engine_version':ENGINE_VERSION,
            'host':{'platform':platform.platform(),'python':platform.python_version(),'processor':platform.processor()},
            'dataset':'Firewall1 variant published by RBAC Maintenance authors','source_url':'https://onlinerbacfixing.github.io/cybersecurity2019/',
            'sha256':hashlib.sha256(raw).hexdigest(),'quality':quality,'counts':result['counts'],
            'baseline':result['baseline'],'cohort_baseline':result['cohort_baseline'],'optimized':result['optimized'],
            'wsc_reduction_percent':round((1-result['optimized']['wsc']/result['baseline']['wsc'])*100,4),
            'reconstruction':{'missing':len(set(rows)-rebuilt),'extra':len(rebuilt-set(rows))},
            'timing':{'runs':len(timings),'wall_ms':timings,'median_ms':statistics.median(timings),'max_ms':max(timings)},
            'memory':{'tracemalloc_peak_bytes':peak,'scope':'Python allocations during compute; excludes interpreter/RSS; separate untimed run'},
            'rl':{'status':'requires_genuine_feedback','synthetic_feedback':False},
            'limits':['Source is static network ACL data, not ERP usage logs.','This source variant has 31,919 grants; commonly cited original Firewall1 has 31,951. No correction or invented grant is made.',
                      'Performance is for this host and dataset; no extrapolated throughput or threat accuracy.']}
    out=ROOT/'docs/evaluation.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
