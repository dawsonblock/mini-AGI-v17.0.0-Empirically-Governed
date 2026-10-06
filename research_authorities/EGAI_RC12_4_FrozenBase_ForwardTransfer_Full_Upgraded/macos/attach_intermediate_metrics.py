#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("bundle"); ap.add_argument("metrics_jsonl"); ap.add_argument("--out",required=True); a=ap.parse_args(); b=json.loads(Path(a.bundle).read_text()); m={}
    for line in Path(a.metrics_jsonl).read_text().splitlines():
        if line.strip():
            x=json.loads(line); cid=str(x["case_id"])
            if cid in m: raise SystemExit(f"duplicate case_id {cid}")
            m[cid]=x
    seen=set()
    for row in b.get("cases") or []:
        cid=str(row.get("case_id")); x=m.get(cid)
        if not x: continue
        seen.add(cid)
        for k in ("state_max_abs_error","logit_max_abs_error","output_token_ids"):
            if k in x: row[k]=x[k]
    if set(m)-seen: raise SystemExit("metrics contain absent case_ids")
    b.pop("bundle_digest",None); b["bundle_digest"]="sha256:"+hashlib.sha256(json.dumps(b,sort_keys=True,separators=(",",":")).encode()).hexdigest(); Path(a.out).write_text(json.dumps(b,indent=2,sort_keys=True)+"\n"); print(f"attached {len(seen)} cases"); return 0
if __name__=="__main__": raise SystemExit(main())
