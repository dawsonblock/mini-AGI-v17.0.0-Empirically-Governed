#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kvcontinual.digests import sha256_json
from kvcontinual.hybrid import HybridModelLayout
from kvcontinual.types import ExecutionIdentity, ModelIdentity


def _text_config(config):
    return getattr(config,"text_config",None) or getattr(config,"language_config",None) or config


def _position_digest(config):
    cfg=_text_config(config)
    return sha256_json({
        "rope_parameters": getattr(cfg,"rope_parameters",None),
        "rope_scaling": getattr(cfg,"rope_scaling",None),
        "rope_theta": getattr(cfg,"rope_theta",None),
        "partial_rotary_factor": getattr(cfg,"partial_rotary_factor",None),
        "max_position_embeddings": getattr(cfg,"max_position_embeddings",None),
    })


def main():
    ap=argparse.ArgumentParser(description="Generate an RC10.18 ExecutionIdentity template bound to a live Qwen config")
    ap.add_argument("model")
    ap.add_argument("--base-weights-digest", required=True)
    ap.add_argument("--tokenizer-digest", required=True)
    ap.add_argument("--adapter-manifest-digest", default="sha256:none")
    ap.add_argument("--quantization-config", default="none")
    ap.add_argument("--activation-dtype", default="float16")
    ap.add_argument("--cache-dtype", default="float32")
    ap.add_argument("--output")
    ap.add_argument("--trust-remote-code", action="store_true")
    a=ap.parse_args()
    import torch, transformers
    from transformers import AutoConfig
    cfg=AutoConfig.from_pretrained(a.model,trust_remote_code=a.trust_remote_code)
    layout=HybridModelLayout.from_config(cfg)
    ident=ExecutionIdentity(
        model=ModelIdentity(
            base_weights=a.base_weights_digest,
            adapter_manifest=a.adapter_manifest_digest,
            tokenizer=a.tokenizer_digest,
            architecture=layout.digest,
            position_config=_position_digest(cfg),
            quantization_config=a.quantization_config,
        ),
        kernel_abi=f"torch={torch.__version__};transformers={transformers.__version__};qwen35-capture=v1",
        recurrence_impl="hf-qwen35-gdn-fixed-input-v1",
        tensor_layout="qwen35-repeat-interleave-kheads;state=[V,Dk,Dv]",
        activation_dtype=a.activation_dtype,
        cache_dtype=a.cache_dtype,
        runtime_learning_state="frozen",
    )
    payload=ident.to_dict()
    raw=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if a.output:
        Path(a.output).write_text(raw)
    else:
        print(raw,end="")

if __name__=="__main__": main()
