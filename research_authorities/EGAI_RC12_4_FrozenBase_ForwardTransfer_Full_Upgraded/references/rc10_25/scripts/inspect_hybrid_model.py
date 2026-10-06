#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from kvcontinual.digests import sha256_json
from kvcontinual.hybrid import HybridModelLayout, build_capture_manifest


def _text_config(config):
    return getattr(config,"text_config",None) or getattr(config,"language_config",None) or config


def _position_payload(config):
    cfg=_text_config(config)
    return {
        "rope_parameters": getattr(cfg,"rope_parameters",None),
        "rope_scaling": getattr(cfg,"rope_scaling",None),
        "rope_theta": getattr(cfg,"rope_theta",None),
        "partial_rotary_factor": getattr(cfg,"partial_rotary_factor",None),
        "max_position_embeddings": getattr(cfg,"max_position_embeddings",None),
    }


def main() -> None:
    p=argparse.ArgumentParser(description="Inspect a Transformers hybrid model config and emit the RC10.18 capture contract")
    p.add_argument("model", help="local model path or Hugging Face model id")
    p.add_argument("--seam", type=int, default=8)
    p.add_argument("--trust-remote-code", action="store_true")
    a=p.parse_args()
    from transformers import AutoConfig
    cfg=AutoConfig.from_pretrained(a.model, trust_remote_code=a.trust_remote_code)
    layout=HybridModelLayout.from_config(cfg)
    manifest=build_capture_manifest(layout,a.seam)
    pos_payload=_position_payload(cfg)
    print(json.dumps({
        "architecture":layout.architecture,
        "layout_digest":layout.digest,
        "position_config_digest":sha256_json(pos_payload),
        "position_config":pos_payload,
        "gdn_layers":layout.gdn_layers,
        "full_attention_layers":layout.full_attention_layers,
        "layers":[{
            "index":x.index,
            "kind":x.kind.value,
            "q_or_value_heads":x.q_heads,
            "kv_or_key_heads":x.kv_heads,
            "key_or_attention_head_dim":x.head_dim,
            "value_head_dim":x.value_head_dim,
            "conv_kernel_size":x.conv_kernel_size,
        } for x in layout.layers],
        "capture_manifest_digest":manifest.digest,
        "seam_width":manifest.seam_width,
        "qwen_gdn_key_head_mapping":"qwen_repeat_interleave",
        "attention_relocation":"model_reapply_pre_rope for Qwen3.5/3.6",
    },indent=2,default=list))

if __name__=="__main__": main()
