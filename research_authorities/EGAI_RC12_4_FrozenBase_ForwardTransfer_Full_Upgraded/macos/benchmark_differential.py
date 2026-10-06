#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,time,urllib.request,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'runtime/src'))
from kvcontinual.execution.platforms.stream_provenance import canonicalize_openai_sse,sha256_obj

def call(endpoint,model,prompt,max_tokens,timeout):
    body={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":0,"stream":True,"stream_options":{"include_usage":True}}
    req=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Accept":"text/event-stream"})
    start=time.perf_counter(); first=None; lines=[]
    with urllib.request.urlopen(req,timeout=timeout) as r:
        for line in r:
            lines.append(line)
            if first is None and b'"content"' in line and b'"content":""' not in line: first=time.perf_counter()
    end=time.perf_counter(); tr=canonicalize_openai_sse(body,lines)
    tokens=tr.usage.get("completion_tokens") or max(1,round(len(tr.assistant_text)/4)); decode=max(1e-9,end-(first or start))
    return {"prompt_digest":sha256_obj(prompt),"request_digest":tr.request_digest,"assistant_text":tr.assistant_text,"assistant_text_digest":tr.assistant_text_digest,"stream_event_chain_digest":tr.event_chain_digest,"stream_event_count":tr.event_count,"malformed_stream_events":tr.malformed_events,"usage":tr.usage,"ttft_s":((first-start) if first else end-start),"total_s":end-start,"decode_tps":float(tokens)/decode}

def prompts(path,single):
    if not path:return [("case-0001",single or "Explain why exact differential qualification matters for cached recurrent-state reuse.")]
    out=[]
    for i,line in enumerate(Path(path).read_text().splitlines(),1):
        if line.strip():
            x=json.loads(line); out.append((str(x.get("case_id") or f"case-{i:04d}"),str(x["prompt"])))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--endpoint",required=True); ap.add_argument("--model",default="local-qwen"); ap.add_argument("--prompts-jsonl"); ap.add_argument("--prompt"); ap.add_argument("--max-tokens",type=int,default=128); ap.add_argument("--timeout",type=float,default=300); ap.add_argument("--mode",choices=["baseline","accelerated"],required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    cases=[]
    for cid,p in prompts(a.prompts_jsonl,a.prompt):
        r=call(a.endpoint,a.model,p,a.max_tokens,a.timeout); r["case_id"]=cid; cases.append(r); print(f"{cid}: ttft={r['ttft_s']:.3f}s decode={r['decode_tps']:.2f} tok/s")
    b={"schema":"egai.apple.differential-run.v1","mode":a.mode,"model":a.model,"cases":cases}; b["bundle_digest"]="sha256:"+hashlib.sha256(json.dumps(b,sort_keys=True,separators=(",",":")).encode()).hexdigest(); Path(a.out).write_text(json.dumps(b,indent=2,sort_keys=True)+"\n"); return 0
if __name__=="__main__": raise SystemExit(main())
