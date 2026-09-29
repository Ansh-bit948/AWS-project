"""Validate and import the attributed Firewall1 permission-to-user matrix."""
from __future__ import annotations
import asyncio, csv, hashlib, io, json, sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RAW=ROOT/"data/raw/firewall1_UPA.txt"
OUT=ROOT/"data/processed/firewall1_upa.csv"
MANIFEST=ROOT/"data/processed/firewall1_manifest.json"
ANALYSIS=ROOT/"data/processed/firewall1_analysis.json"
SOURCE="https://onlinerbacfixing.github.io/cybersecurity2019/"
LICENSE="CC BY 4.0; attribution: On the Use of Max-SAT and PDDL in RBAC Maintenance, Firewall1 dataset"
def sha(data): return hashlib.sha256(data).hexdigest()
def main():
 raw=RAW.read_bytes(); lines=[line.split() for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
 if not lines or any(not row or any(bit not in {"0","1"} for bit in row) for row in lines): raise ValueError("Expected a nonempty whitespace-delimited binary matrix")
 widths={len(row) for row in lines}
 if len(widths)!=1: raise ValueError(f"Ragged matrix widths: {sorted(widths)}")
 users=len(lines); permissions=widths.pop(); OUT.parent.mkdir(parents=True,exist_ok=True)
 with OUT.open("w",newline="",encoding="utf-8") as f:
  writer=csv.writer(f); writer.writerow(("user_id","permission_id"))
  for ri,row in enumerate(lines,1): writer.writerows((f"U{ri:04d}",f"P{ci:04d}") for ci,bit in enumerate(row,1) if bit=="1")
 derived=OUT.read_bytes(); edges=sum(bit=="1" for row in lines for bit in row)
 manifest={"source_url":SOURCE,"source_title":"Firewall1 permission-to-user ACL matrix","license":LICENSE,"attribution_url":"https://creativecommons.org/licenses/by/4.0/","retrieved_at_utc":datetime.now(timezone.utc).isoformat(),"orientation":"source rows=users; source columns=permissions; each 1 is an observed grant","identifier_note":"U/P labels are positional labels for matrix row/column indices, not real identities or attributes","raw_path":"data/raw/firewall1_UPA.txt","raw_sha256":sha(raw),"derived_path":"data/processed/firewall1_upa.csv","derived_sha256":sha(derived),"dimensions":{"users":users,"permissions":permissions},"observed_grants":edges,"validation":{"binary_cells_only":True,"rectangular":True,"all_cells_checked":users*permissions}}
 async def run():
  from app.main import import_csv, analytics
  result=await import_csv(UploadFile(filename=OUT.name,file=io.BytesIO(derived)),name="Firewall1 published ACL benchmark",source_url=SOURCE,license_note=LICENSE)
  result["analysis"]=analytics(result["dataset_id"])["analysis"]; return result
 result=asyncio.run(run()); manifest["application_import"]={k:result[k] for k in ("dataset_id","run_id","sha256","counts")}
 MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8"); ANALYSIS.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"counts":result["counts"],"baseline":result["analysis"]["baseline"],"optimized":result["analysis"]["optimized"],"risk_findings":result["analysis"]["risk_findings_total"]},indent=2))
if __name__=="__main__": main()
