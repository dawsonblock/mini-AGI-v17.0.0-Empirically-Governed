#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
BASE=[("arithmetic","Compute 173 * 29. Return only the integer."),("code","Write a Python function that returns the nth Fibonacci number iteratively."),("json","Return JSON with keys a,b,c and values 1,2,3. No markdown."),("reasoning","A cache contains blocks A,B,C. B changes. Explain which cached state must be invalidated and why."),("unicode","Repeat exactly: naïve façade — 東京 — Δx=0.125"),("boundary","Number the integers from 1 through 64 separated by commas."),("repetition","Summarize in one sentence: "+("observed evidence is not simulated evidence; "*64)),("tools","Given read(path) and write(path,text), describe the minimal safe sequence to copy a file after verifying its digest.")]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); ap.add_argument("--cases",type=int,default=64); a=ap.parse_args(); rows=[]
    for i in range(a.cases):
        n,p=BASE[i%len(BASE)]; prompt=f"[equivalence-case={i:04d}; variant={i//len(BASE)}]\n{p}"; rows.append({"case_id":f"eq-{i:04d}-{n}","prompt":prompt,"prompt_sha256":"sha256:"+hashlib.sha256(prompt.encode()).hexdigest()})
    Path(a.out).write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in rows)); print(f"wrote {len(rows)} cases"); return 0
if __name__=="__main__": raise SystemExit(main())
