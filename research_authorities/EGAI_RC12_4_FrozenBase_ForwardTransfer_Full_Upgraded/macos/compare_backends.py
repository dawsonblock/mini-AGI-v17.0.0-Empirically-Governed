#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--name-a",default="A"); ap.add_argument("--name-b",default="B"); ap.add_argument("--out"); x=ap.parse_args(); a=json.loads(Path(x.a).read_text())["summary"]; b=json.loads(Path(x.b).read_text())["summary"]; ratio=lambda n,d:(float(n)/float(d)) if d not in (None,0) else None; r={"schema":"egai.apple.backend-comparison.v1","a":x.name_a,"b":x.name_b,"metrics":{"ttft_ratio_b_over_a":ratio(b.get("ttft_median_s"),a.get("ttft_median_s")),"decode_speedup_b_over_a":ratio(b.get("decode_tps_median"),a.get("decode_tps_median")),"total_ratio_b_over_a":ratio(b.get("total_median_s"),a.get("total_median_s"))},"raw":{"a":a,"b":b}}; raw=json.dumps(r,indent=2,sort_keys=True)+"\n"; print(raw,end=""); Path(x.out).write_text(raw) if x.out else None; return 0
if __name__=="__main__": raise SystemExit(main())
