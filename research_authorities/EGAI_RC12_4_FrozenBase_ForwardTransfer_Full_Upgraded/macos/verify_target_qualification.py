#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'runtime/src'))
from kvcontinual.execution.platforms.target_mac_qualification import verify_target_mac_evidence
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("evidence"); a=ap.parse_args(); p=json.loads(Path(a.evidence).read_text()); ok=verify_target_mac_evidence(p); print(json.dumps({"valid":ok,"passed":bool(p.get("passed_local_differential_gates")),"evidence_digest":p.get("evidence_digest")},indent=2)); return 0 if ok else 2
if __name__=="__main__": raise SystemExit(main())
