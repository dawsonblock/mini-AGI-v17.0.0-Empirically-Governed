#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'runtime/src'))
from kvcontinual.execution.platforms.target_mac_qualification import *
def cmd(x):
    try:return subprocess.check_output(x,text=True,stderr=subprocess.STDOUT,timeout=10).strip()
    except Exception:return ""
def d(v):
    if v.startswith("sha256:"):return v
    p=Path(v)
    if p.is_file():return digest_file(p)
    if p.is_dir():return digest_tree(p)
    raise SystemExit(f"cannot digest {v}")
def hw():return {"platform":platform.platform(),"machine":platform.machine(),"macos":cmd(["sw_vers","-productVersion"]),"hardware_model":cmd(["sysctl","-n","hw.model"]),"chip":cmd(["sysctl","-n","machdep.cpu.brand_string"]),"memory_bytes":cmd(["sysctl","-n","hw.memsize"]),"python":sys.version.split()[0],"mlx":cmd([sys.executable,"-c","import mlx; print(getattr(mlx,'__version__','unknown'))"]),"llama_server":cmd(["llama-server","--version"])}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--baseline-json",required=True); ap.add_argument("--accelerated-json",required=True); ap.add_argument("--model",required=True); ap.add_argument("--tokenizer",required=True); ap.add_argument("--source-closure",default=str(ROOT/'release/RC12_3_1_TARGET_MAC_SOURCE_CLOSURE.json')); ap.add_argument("--adapter",default="sha256:"+"0"*64); ap.add_argument("--execution-policy",default="sha256:"+"0"*64); ap.add_argument("--backend",required=True,choices=["mlx","llama.cpp","native-metal"]); ap.add_argument("--precision",default="fp16"); ap.add_argument("--quantization",default="none"); ap.add_argument("--min-cases",type=int,default=32); ap.add_argument("--exact-text-fraction",type=float,default=1.0); ap.add_argument("--exact-token-fraction",type=float,default=1.0); ap.add_argument("--require-token-ids",action="store_true"); ap.add_argument("--require-intermediate-metrics",action="store_true"); ap.add_argument("--max-state-abs-error",type=float,default=1e-5); ap.add_argument("--max-logit-abs-error",type=float,default=1e-4); ap.add_argument("--max-ttft-ratio",type=float,default=1.0); ap.add_argument("--min-decode-speedup",type=float,default=1.0); ap.add_argument("--notes",default=""); ap.add_argument("--out",required=True); a=ap.parse_args()
    if platform.system()!="Darwin" or platform.machine()!="arm64": print("ERROR: target-Mac qualification requires Darwin arm64",file=sys.stderr); return 7
    sc=json.loads(Path(a.source_closure).read_text()); hp=hw(); ident=TargetMacRuntimeIdentity(d(a.model),d(a.tokenizer),str(sc.get("closure_digest") or digest_obj(sc)),digest_obj(hp),a.backend,a.precision,a.quantization,d(a.adapter),d(a.execution_policy)); th=EquivalenceThresholds(a.min_cases,a.exact_text_fraction,a.exact_token_fraction,a.require_token_ids,a.require_intermediate_metrics,a.max_state_abs_error,a.max_logit_abs_error,a.max_ttft_ratio,a.min_decode_speedup); e=build_target_mac_evidence(identity=ident,baseline=json.loads(Path(a.baseline_json).read_text()),accelerated=json.loads(Path(a.accelerated_json).read_text()),thresholds=th,hardware_profile=hp,notes=a.notes); Path(a.out).write_text(json.dumps(e,indent=2,sort_keys=True)+"\n"); print(json.dumps({"passed":e["passed_local_differential_gates"],"evidence_digest":e["evidence_digest"],"gates":e["gates"]},indent=2)); return 0 if e["passed_local_differential_gates"] else 9
if __name__=="__main__": raise SystemExit(main())
