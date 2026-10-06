#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kvcontinual.cache import save_execution_artifact
from kvcontinual.digests import sha256_json
from kvcontinual.hybrid import HybridModelLayout, build_capture_manifest
from kvcontinual.hybrid.materialize import MaterializationInputs, materialize_execution_artifact
from kvcontinual.hybrid.qwen35_transformers import Qwen35TransformersLiveCapture
from kvcontinual.types import ExecutionIdentity, ModelIdentity


def _load_identity(path: str | Path) -> ExecutionIdentity:
    raw=json.loads(Path(path).read_text())
    if "model" not in raw:
        raise ValueError("identity JSON must contain a 'model' object")
    model=ModelIdentity(**raw["model"])
    fields={k:v for k,v in raw.items() if k not in ("model","digest")}
    ident=ExecutionIdentity(model=model, **fields)
    supplied=raw.get("digest")
    if supplied and supplied != ident.digest:
        raise ValueError("identity JSON digest does not match its fields")
    return ident


def _text_config(config):
    return getattr(config,"text_config",None) or getattr(config,"language_config",None) or config


def _position_digest(config) -> str:
    cfg=_text_config(config)
    payload={
        "rope_parameters": getattr(cfg,"rope_parameters",None),
        "rope_scaling": getattr(cfg,"rope_scaling",None),
        "rope_theta": getattr(cfg,"rope_theta",None),
        "partial_rotary_factor": getattr(cfg,"partial_rotary_factor",None),
        "max_position_embeddings": getattr(cfg,"max_position_embeddings",None),
    }
    return sha256_json(payload)


def main() -> None:
    ap=argparse.ArgumentParser(description="Capture one text-only Qwen3.5/3.6 source segment into an RC10.18 execution artifact")
    ap.add_argument("model", help="local model path or Hugging Face model id")
    src=ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="text to tokenize as one independent source segment")
    src.add_argument("--tokens-json", help="JSON file containing a list of token ids")
    ap.add_argument("--identity-json", required=True, help="exact ExecutionIdentity JSON; cache validity depends on this")
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--output", required=True, help="output .npz path")
    ap.add_argument("--seam", type=int, default=8)
    ap.add_argument("--dtype", choices=("float16","bfloat16","float32"), default="float16")
    ap.add_argument("--device", choices=("mps","cpu"), default=None)
    ap.add_argument("--trust-remote-code", action="store_true")
    args=ap.parse_args()

    import torch, transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    identity=_load_identity(args.identity_json)
    expected_kernel_abi=f"torch={torch.__version__};transformers={transformers.__version__};qwen35-capture=v1"
    if identity.kernel_abi != expected_kernel_abi:
        raise RuntimeError(
            f"identity kernel_abi mismatch: identity={identity.kernel_abi} live={expected_kernel_abi}"
        )
    dtype={"float16":torch.float16,"bfloat16":torch.bfloat16,"float32":torch.float32}[args.dtype]
    device=args.device or ("mps" if torch.backends.mps.is_available() else "cpu")

    model=AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=dtype, trust_remote_code=args.trust_remote_code
    )
    model.to(device).eval()
    cfg=_text_config(model.config)
    layout=HybridModelLayout.from_config(model.config)
    manifest=build_capture_manifest(layout,args.seam)

    # Refuse to capture under an identity whose architecture/position claims do
    # not match the live model configuration. Base-weight and tokenizer hashes
    # remain operator-supplied because they must bind the exact local artifacts.
    if identity.model.architecture != layout.digest:
        raise RuntimeError(
            f"identity architecture mismatch: identity={identity.model.architecture} live={layout.digest}"
        )
    pos_digest=_position_digest(model.config)
    if identity.model.position_config != pos_digest:
        raise RuntimeError(
            f"identity position_config mismatch: identity={identity.model.position_config} live={pos_digest}"
        )

    if args.tokens_json:
        tokens=json.loads(Path(args.tokens_json).read_text())
        if not isinstance(tokens,list) or not tokens or any(not isinstance(x,int) for x in tokens):
            raise ValueError("tokens JSON must be a non-empty list of integers")
    else:
        tok=AutoTokenizer.from_pretrained(args.model, trust_remote_code=args.trust_remote_code)
        tokens=tok(args.text, add_special_tokens=False)["input_ids"]
    if len(tokens) <= args.seam:
        raise ValueError("source segment must contain tokens beyond the fixed seam")

    input_ids=torch.tensor([tokens],dtype=torch.long,device=device)
    attention_mask=torch.ones_like(input_ids)
    capture_adapter=Qwen35TransformersLiveCapture(model,manifest,source_position_start=0)
    capture,_=capture_adapter.capture_prefill(input_ids=input_ids,attention_mask=attention_mask)

    conv_sizes={s.index:s.conv_kernel_size for s in layout.layers if s.conv_kernel_size > 0}
    constants=MaterializationInputs.for_qwen35(
        conv_kernel_size_by_layer=conv_sizes,
        position_config_digest=pos_digest,
        attention_layers=list(layout.full_attention_layers),
    )
    artifact=materialize_execution_artifact(
        source_segment_id=args.source_id,
        source_tokens=tokens,
        identity=identity,
        capture=capture,
        constants=constants,
    )
    out=save_execution_artifact(args.output,artifact)
    print(json.dumps({
        "output":str(out),
        "source_segment_id":artifact.source_segment_id,
        "tokens":len(tokens),
        "execution_identity":artifact.identity.digest,
        "capture_manifest_digest":artifact.capture_manifest_digest,
        "artifact_content_digest":artifact.content_digest,
        "recurrent_heads":len(artifact.recurrent),
        "attention_layers":sorted(artifact.attention),
        "conv_layers":sorted(artifact.conv_boundaries),
        "byte_size":artifact.byte_size,
        "hypic_qualified":artifact.hypic_qualified,
        "note":"Capture/materialization does not itself qualify artifact reuse; exact-oracle qualification is still required.",
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
