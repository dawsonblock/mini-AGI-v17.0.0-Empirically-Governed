#!/usr/bin/env python3
import argparse,json,statistics,time,urllib.request
from pathlib import Path
def call(endpoint,model,prompt,max_tokens,timeout):
    body={"model":model,"messages":[{"role":"user","content":prompt}],"temperature":0,"max_tokens":max_tokens,"stream":True,"stream_options":{"include_usage":True}}; req=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Accept":"text/event-stream"}); start=time.perf_counter(); first=None
    with urllib.request.urlopen(req,timeout=timeout) as r:
        for raw in r:
            if first is None and b'"content"' in raw and b'"content":""' not in raw:first=time.perf_counter()
    end=time.perf_counter(); return {"ttft_s":((first-start) if first else end-start),"total_s":end-start}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--endpoint",default="http://127.0.0.1:8088/v1/chat/completions"); ap.add_argument("--model",default="local-qwen"); ap.add_argument("--prompt-file",required=True); ap.add_argument("--warm-runs",type=int,default=5); ap.add_argument("--max-tokens",type=int,default=64); ap.add_argument("--timeout",type=float,default=300); ap.add_argument("--out",required=True); a=ap.parse_args(); p=Path(a.prompt_file).read_text(); cold=call(a.endpoint,a.model,p,a.max_tokens,a.timeout); warm=[call(a.endpoint,a.model,p,a.max_tokens,a.timeout) for _ in range(a.warm_runs)]; wm=statistics.median(x["ttft_s"] for x in warm); result={"schema":"egai.apple.context-reuse-benchmark.v1","cold":cold,"warm_runs":warm,"summary":{"cold_ttft_s":cold["ttft_s"],"warm_ttft_median_s":wm,"ttft_speedup":cold["ttft_s"]/wm if wm else None},"caveat":"Diagnostic only unless backend cache-hit/reuse metadata is independently bound."}; Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result["summary"],indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
