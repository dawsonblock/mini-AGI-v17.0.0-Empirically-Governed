#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from kvcontinual.cache import load_execution_artifact


def main() -> None:
    p=argparse.ArgumentParser(description="Validate an RC10.18 persisted execution artifact")
    p.add_argument("artifact", help=".npz execution artifact")
    a=p.parse_args()
    art=load_execution_artifact(a.artifact)
    print(json.dumps({
        "source_segment_id": art.source_segment_id,
        "execution_identity": art.identity.digest,
        "content_digest": art.content_digest,
        "capture_manifest_digest": art.capture_manifest_digest,
        "seam_width": art.fixed_seam_width,
        "recurrent_heads": len(art.recurrent),
        "attention_layers": sorted(art.attention),
        "conv_layers": sorted(art.conv_boundaries),
        "byte_size": art.byte_size,
        "hypic_qualified": art.hypic_qualified,
    }, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
