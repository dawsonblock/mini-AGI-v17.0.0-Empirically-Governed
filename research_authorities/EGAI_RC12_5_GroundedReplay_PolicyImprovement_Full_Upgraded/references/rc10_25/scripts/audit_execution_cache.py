#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kvcontinual.cache.serialization import load_execution_artifact


def main() -> int:
    ap=argparse.ArgumentParser(description="Audit an RC10.21 persistent execution-cache root")
    ap.add_argument("root")
    args=ap.parse_args()
    root=Path(args.root)
    index=root/"index"; objects=root/"objects"
    referenced=set(); valid=0; invalid=[]
    for idx in sorted(index.glob("*/*.json")):
        try:
            meta=json.loads(idx.read_text())
            storage=str(meta["storage_digest"])
            hexv=storage.split(":",1)[1]
            referenced.add(hexv)
            obj=objects/f"{hexv}.npz"
            art=load_execution_artifact(obj)
            if art.content_digest != meta["content_digest"]:
                raise ValueError("content digest mismatch")
            if art.identity.digest != meta["execution_identity_digest"]:
                raise ValueError("execution identity mismatch")
            if art.source_segment_id != meta["source_segment_id"]:
                raise ValueError("source segment mismatch")
            valid += 1
        except Exception as exc:
            invalid.append({"index":str(idx),"error":str(exc)})
    orphan=[str(p) for p in sorted(objects.glob("*.npz")) if p.stem not in referenced]
    result={"valid_indexes":valid,"invalid_indexes":invalid,"orphan_objects":orphan,"passed":not invalid}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["passed"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
