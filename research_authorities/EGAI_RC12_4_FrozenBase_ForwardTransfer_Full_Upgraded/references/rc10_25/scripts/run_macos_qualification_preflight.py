#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from kvcontinual.macos_qualification_preflight import run_macos_qualification_preflight,write_preflight
p=argparse.ArgumentParser(description="Fail-closed RC10.25 Apple-Silicon qualification preflight")
p.add_argument("--backend-fingerprint",required=True); p.add_argument("--out",default="qualification/preflight.json"); p.add_argument("--require-mlx",action="store_true")
a=p.parse_args(); r=run_macos_qualification_preflight(backend_fingerprint=a.backend_fingerprint,require_mlx=a.require_mlx); write_preflight(r,a.out)
print(json.dumps(r.to_dict(),indent=2,sort_keys=True)); sys.exit(0 if r.passed else 2)
