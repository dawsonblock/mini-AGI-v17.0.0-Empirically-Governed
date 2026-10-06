#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from kvcontinual.hardware_qualification import detect_hardware_runtime_fingerprint

p=argparse.ArgumentParser(description="Emit the exact macOS/Apple-Silicon runtime fingerprint used by RC10.24 qualification.")
p.add_argument("--backend-fingerprint", required=True)
p.add_argument("--out")
a=p.parse_args()
fp=detect_hardware_runtime_fingerprint(backend_fingerprint=a.backend_fingerprint)
text=json.dumps(fp.to_dict(), indent=2, sort_keys=True)+"\n"
if a.out:
    open(a.out,"w",encoding="utf-8").write(text)
else:
    print(text,end="")
