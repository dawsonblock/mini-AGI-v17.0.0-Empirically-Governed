from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any
import numpy as np

from kvcontinual.rc1025.attention.relocation import FullAttentionRelocationMetadata
from kvcontinual.rc1025.cache.block import (
    ArtifactQualification, BoundaryAnchors, ExecutionArtifact,
    FullAttentionLayerArtifact, RecurrentTailArtifact,
)
from kvcontinual.rc1025.recurrent.affine import AffineSummary
from kvcontinual.rc1025.recurrent.conv_boundary import ConvBoundaryState, ConvDecodeState
from kvcontinual.rc1025.types import CacheTier, ExecutionIdentity, ModelIdentity, TransitionOrientation


_FORMAT = "kvcontinual-execution-artifact-v4"
_LEGACY_REGENERATE = {"kvcontinual-execution-artifact-v1", "kvcontinual-execution-artifact-v2", "kvcontinual-execution-artifact-v3"}


def _identity_to_dict(x: ExecutionIdentity) -> dict[str, Any]:
    return {
        "model": asdict(x.model),
        "kernel_abi": x.kernel_abi,
        "recurrence_impl": x.recurrence_impl,
        "tensor_layout": x.tensor_layout,
        "activation_dtype": x.activation_dtype,
        "cache_dtype": x.cache_dtype,
        "runtime_learning_state": x.runtime_learning_state,
    }


def _identity_from_dict(x: dict[str, Any]) -> ExecutionIdentity:
    return ExecutionIdentity(ModelIdentity(**x["model"]), **{k:v for k,v in x.items() if k != "model"})


def save_execution_artifact(path: str | Path, artifact: ExecutionArtifact) -> Path:
    """Write one execution artifact as JSON metadata + numeric NPZ arrays.

    No Python pickle objects are stored. The persisted object is disposable cache
    state and always carries its content digest and exact execution identity.
    """
    artifact.validate()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, np.ndarray] = {}
    recurrent_meta = []
    for i, key in enumerate(sorted(artifact.recurrent)):
        r = artifact.recurrent[key]
        tkey, zkey = f"r{i}_T", f"r{i}_Z"
        arrays[tkey] = np.asarray(r.tail_summary.T)
        arrays[zkey] = np.asarray(r.tail_summary.Z)
        convkey = None
        if r.trailing_conv_payload is not None:
            convkey = f"r{i}_trailconv"
            arrays[convkey] = np.asarray(r.trailing_conv_payload)
        recurrent_meta.append({
            "layer": r.layer, "head": r.head, "seam_width": r.seam_width,
            "orientation": r.tail_summary.orientation.value,
            "T": tkey, "Z": zkey, "trailing_conv_payload": convkey,
            "stats": r.stats, "key_head": r.key_head, "key_head_mapping": r.key_head_mapping,
        })

    conv_meta = []
    for i, layer in enumerate(sorted(artifact.conv_boundaries)):
        c = artifact.conv_boundaries[layer]
        key = f"conv{i}"
        arrays[key] = np.asarray(c.history)
        conv_meta.append({"layer": layer, "kernel_size": c.kernel_size, "history": key})

    conv_decode_meta = []
    for i, layer in enumerate(sorted(artifact.conv_decode_states)):
        c = artifact.conv_decode_states[layer]
        key = f"conv_decode{i}"
        arrays[key] = np.asarray(c.history)
        conv_decode_meta.append({"layer": layer, "kernel_size": c.kernel_size, "history": key})

    attention_meta = []
    for i, layer in enumerate(sorted(artifact.attention)):
        a = artifact.attention[layer]
        kk, vk, pk = f"attn{i}_k", f"attn{i}_v", f"attn{i}_p"
        arrays[kk] = np.asarray(a.pre_rope_keys)
        arrays[vk] = np.asarray(a.values)
        arrays[pk] = np.asarray(a.source_positions)
        attention_meta.append({
            "layer": layer, "pre_rope_keys": kk, "values": vk,
            "source_positions": pk, "relocation": asdict(a.relocation),
        })

    boundary_meta = {"leading_tokens": artifact.boundary.leading_tokens, "original_hidden": {}, "original_attention_output": {}, "original_route_ids": {}}
    for group_name in ("original_hidden", "original_attention_output", "original_route_ids"):
        group = getattr(artifact.boundary, group_name)
        for layer, value in sorted(group.items()):
            key = f"boundary_{group_name}_{layer}"
            arrays[key] = np.asarray(value)
            boundary_meta[group_name][str(layer)] = key

    metadata = {
        "format": _FORMAT,
        "source_segment_id": artifact.source_segment_id,
        "source_token_digest": artifact.source_token_digest,
        "identity": _identity_to_dict(artifact.identity),
        "identity_digest": artifact.identity.digest,
        "fixed_seam_width": artifact.fixed_seam_width,
        "attention_kv_ref": artifact.attention_kv_ref,
        "position_metadata": artifact.position_metadata,
        "capture_manifest_digest": artifact.capture_manifest_digest,
        "qualification": None if artifact.qualification is None else asdict(artifact.qualification),
        "tier": artifact.tier.value,
        "byte_size": artifact.byte_size,
        "artifact_id": artifact.artifact_id,
        "created_at": artifact.created_at,
        "content_digest": artifact.content_digest,
        "recurrent": recurrent_meta,
        "conv_boundaries": conv_meta,
        "conv_decode_states": conv_decode_meta,
        "attention": attention_meta,
        "attention_relocation_only": {
            str(layer): asdict(meta) for layer, meta in sorted(artifact.attention_relocation.items()) if layer not in artifact.attention
        },
        "boundary": boundary_meta,
    }
    meta_bytes = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    arrays["__metadata_utf8__"] = np.frombuffer(meta_bytes, dtype=np.uint8)
    np.savez_compressed(p, **arrays)
    return p


def load_execution_artifact(path: str | Path) -> ExecutionArtifact:
    p = Path(path)
    with np.load(p, allow_pickle=False) as data:
        if "__metadata_utf8__" not in data.files:
            raise ValueError("execution artifact archive has no metadata")
        metadata = json.loads(np.asarray(data["__metadata_utf8__"], dtype=np.uint8).tobytes().decode("utf-8"))
        fmt = metadata.get("format")
        if fmt in _LEGACY_REGENERATE:
            raise ValueError(
                "legacy execution artifact must be regenerated from authoritative source tokens: "
                "RC10.21 requires source binding plus distinct seam/decode convolution state"
            )
        if fmt != _FORMAT:
            raise ValueError("unsupported execution artifact format")
        identity = _identity_from_dict(metadata["identity"])
        if identity.digest != metadata["identity_digest"]:
            raise ValueError("persisted execution identity digest mismatch")

        recurrent = {}
        for r in metadata["recurrent"]:
            summary = AffineSummary(np.asarray(data[r["T"]]), np.asarray(data[r["Z"]]), TransitionOrientation(r["orientation"]))
            trail = None if r["trailing_conv_payload"] is None else np.asarray(data[r["trailing_conv_payload"]])
            item = RecurrentTailArtifact(
                r["layer"], r["head"], r["seam_width"], summary, trail, dict(r["stats"]),
                r.get("key_head"), r.get("key_head_mapping", "legacy_unspecified"),
            )
            recurrent[(item.layer, item.head)] = item

        conv = {}
        for c in metadata["conv_boundaries"]:
            conv[int(c["layer"])] = ConvBoundaryState(np.asarray(data[c["history"]]), int(c["kernel_size"]))

        conv_decode = {}
        for c in metadata.get("conv_decode_states", []):
            conv_decode[int(c["layer"])] = ConvDecodeState(np.asarray(data[c["history"]]), int(c["kernel_size"]))

        attention = {}
        relocation = {}
        for a in metadata["attention"]:
            meta = FullAttentionRelocationMetadata(**a["relocation"])
            item = FullAttentionLayerArtifact(
                int(a["layer"]), np.asarray(data[a["pre_rope_keys"]]), np.asarray(data[a["values"]]),
                np.asarray(data[a["source_positions"]]), meta,
            )
            attention[item.layer] = item
            relocation[item.layer] = meta
        for layer, raw in metadata.get("attention_relocation_only", {}).items():
            relocation[int(layer)] = FullAttentionRelocationMetadata(**raw)

        bm = metadata["boundary"]
        boundary = BoundaryAnchors(leading_tokens=list(bm["leading_tokens"]))
        for group_name in ("original_hidden", "original_attention_output", "original_route_ids"):
            group = getattr(boundary, group_name)
            for layer, key in bm[group_name].items():
                group[int(layer)] = np.asarray(data[key])

        qraw = metadata["qualification"]
        qualification = None if qraw is None else ArtifactQualification(**qraw)
        art = ExecutionArtifact(
            source_segment_id=metadata["source_segment_id"], identity=identity,
            fixed_seam_width=int(metadata["fixed_seam_width"]), recurrent=recurrent,
            source_token_digest=metadata["source_token_digest"],
            attention_kv_ref=metadata["attention_kv_ref"], position_metadata=dict(metadata["position_metadata"]),
            boundary=boundary, conv_boundaries=conv, conv_decode_states=conv_decode, attention_relocation=relocation, attention=attention,
            capture_manifest_digest=metadata["capture_manifest_digest"], qualification=qualification,
            tier=CacheTier(metadata["tier"]), byte_size=int(metadata["byte_size"]),
            artifact_id=metadata["artifact_id"], created_at=metadata["created_at"],
        )
    if art.content_digest != metadata["content_digest"]:
        raise ValueError("persisted execution artifact content digest mismatch")
    art.validate()
    return art
