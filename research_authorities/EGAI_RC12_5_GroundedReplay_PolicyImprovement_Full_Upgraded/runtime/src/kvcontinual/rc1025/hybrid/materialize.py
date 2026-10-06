from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
import hashlib
import json
import numpy as np

from kvcontinual.rc1025.attention.relocation import (
    AttentionRelocationStrategy, FullAttentionRelocationMetadata, rope_digest,
)
from kvcontinual.rc1025.cache.block import (
    BoundaryAnchors,
    ExecutionArtifact,
    FullAttentionLayerArtifact,
    RecurrentTailArtifact,
)
from kvcontinual.rc1025.hybrid.capture_buffer import HybridCaptureBuffer
from kvcontinual.rc1025.recurrent.conv_boundary import ConvBoundaryState, ConvDecodeState
from kvcontinual.rc1025.recurrent.hypic_capture import capture_segment_tail_heads
from kvcontinual.rc1025.types import ExecutionIdentity


@dataclass(frozen=True)
class MaterializationInputs:
    """Immutable model-side constants required to compile live captures.

    Qwen3.5 stores pre-RoPE keys and must reapply the deployed model's own
    interleaved MRoPE at target positions. Generic pairwise RoPE remains
    available only for models whose position scheme is actually compatible.
    """
    rope_inv_freq_by_layer: Mapping[int, np.ndarray]
    conv_kernel_size_by_layer: Mapping[int, int]
    attention_strategy_by_layer: Mapping[int, str] = field(default_factory=dict)
    position_embedding_digest_by_layer: Mapping[int, str] = field(default_factory=dict)

    @classmethod
    def for_qwen35(cls, *, conv_kernel_size_by_layer: Mapping[int, int], position_config_digest: str, attention_layers: list[int]):
        return cls(
            rope_inv_freq_by_layer={},
            conv_kernel_size_by_layer=conv_kernel_size_by_layer,
            attention_strategy_by_layer={i: AttentionRelocationStrategy.MODEL_REAPPLY_PRE_ROPE.value for i in attention_layers},
            position_embedding_digest_by_layer={i: position_config_digest for i in attention_layers},
        )


def _token_count_from_capture(buffer: HybridCaptureBuffer) -> int:
    counts: set[int] = set()
    for c in buffer.gdn.values():
        counts.add(int(np.asarray(c.k).shape[0]))
        counts.add(int(np.asarray(c.v).shape[0]))
    for c in buffer.attention.values():
        counts.add(int(np.asarray(c.pre_rope_keys).shape[0]))
        counts.add(int(np.asarray(c.values).shape[0]))
    if len(counts) != 1:
        raise ValueError(f"capture token counts disagree: {sorted(counts)}")
    return counts.pop()


def materialize_execution_artifact(
    *,
    source_segment_id: str,
    source_tokens: list[int],
    identity: ExecutionIdentity,
    capture: HybridCaptureBuffer,
    constants: MaterializationInputs,
) -> ExecutionArtifact:
    """Compile a complete live capture into an execution artifact.

    This function is deliberately independent of Transformers internals. A live
    model integration must first populate ``HybridCaptureBuffer`` from the exact
    current model execution; only then can the cache artifact be materialized.
    """
    missing = capture.missing_requirements()
    if missing:
        raise ValueError("capture is incomplete: " + ", ".join(missing))
    seam = int(capture.manifest.seam_width)
    token_count = _token_count_from_capture(capture)
    if token_count != len(source_tokens):
        raise ValueError("source token count does not match live capture")
    if token_count <= seam:
        raise ValueError("segment must contain tokens beyond the fixed seam")

    recurrent: dict[tuple[int, int], RecurrentTailArtifact] = {}
    conv: dict[int, ConvBoundaryState] = {}
    conv_decode: dict[int, ConvDecodeState] = {}
    anchors = BoundaryAnchors(leading_tokens=list(source_tokens[:seam]))

    for layer, c in sorted(capture.gdn.items()):
        heads = capture_segment_tail_heads(c.k, c.v, c.decay, c.beta, seam_width=seam, key_head_mapping=c.key_head_mapping)
        for vh, summary in enumerate(heads.summaries):
            recurrent[(layer, vh)] = RecurrentTailArtifact(
                layer=layer,
                head=vh,
                seam_width=seam,
                tail_summary=summary,
                # Convolution boundary state is stored once per layer below; do not
                # duplicate the same potentially-large payload in every value head.
                trailing_conv_payload=None,
                stats={
                    "tokens": float(token_count),
                    "key_head_dim": float(heads.key_head_dim),
                    "value_head_dim": float(heads.value_head_dim),
                },
                key_head=heads.key_head_for_value[vh],
                key_head_mapping=heads.key_head_mapping.value,
            )
        kernel = int(constants.conv_kernel_size_by_layer.get(layer, 1))
        conv_input = np.asarray(c.conv_input)
        if conv_input.ndim != 2 or conv_input.shape[0] != token_count:
            raise ValueError(f"layer {layer}: conv_input must be token-major [T,C]")
        keep = max(0, kernel - 1)
        if keep:
            if token_count < keep:
                raise ValueError(f"layer {layer}: segment shorter than causal-convolution history")
            hist = conv_input[-keep:].T.copy()
        else:
            hist = np.empty((conv_input.shape[1], 0), dtype=conv_input.dtype)
        # This is the OUTGOING predecessor history after the whole source segment.
        # It is what the next relocated segment needs to reconstruct its fresh seam.
        conv[layer] = ConvBoundaryState(history=hist, kernel_size=kernel)
        # Native single-token decode caches (including current Transformers)
        # keep K raw projected samples, not the K-1 predecessor samples above.
        if kernel > 0:
            if token_count < kernel:
                pad = np.zeros((kernel - token_count, conv_input.shape[1]), dtype=conv_input.dtype)
                decode_hist = np.concatenate([pad, conv_input], axis=0).T.copy()
            else:
                decode_hist = conv_input[-kernel:].T.copy()
            conv_decode[layer] = ConvDecodeState(history=decode_hist, kernel_size=kernel)
        if c.boundary_hidden is not None:
            anchors.original_hidden[layer] = np.asarray(c.boundary_hidden).copy()

    attention: dict[int, FullAttentionLayerArtifact] = {}
    relocation: dict[int, FullAttentionRelocationMetadata] = {}
    for layer, c in sorted(capture.attention.items()):
        k = np.asarray(c.pre_rope_keys)
        v = np.asarray(c.values)
        pos = np.asarray(c.source_positions, dtype=np.int64)
        if pos.ndim != 1 or pos.shape[0] != token_count:
            raise ValueError(f"layer {layer}: invalid source positions")
        strategy = AttentionRelocationStrategy(
            constants.attention_strategy_by_layer.get(layer, AttentionRelocationStrategy.PAIRWISE_ROPE_DELTA.value)
        )
        if strategy == AttentionRelocationStrategy.MODEL_REAPPLY_PRE_ROPE:
            position_digest = constants.position_embedding_digest_by_layer.get(layer) or identity.model.position_config
            if not position_digest:
                raise ValueError(f"layer {layer}: model-reapply position strategy requires a position-config digest")
            rdigest = position_digest
        else:
            if layer not in constants.rope_inv_freq_by_layer:
                raise ValueError(f"layer {layer}: ordinary RoPE relocation requires inv_freq")
            rdigest = rope_digest(np.asarray(constants.rope_inv_freq_by_layer[layer]))
        meta = FullAttentionRelocationMetadata(
            layer=layer,
            token_count=token_count,
            source_position_start=int(pos[0]) if len(pos) else 0,
            keys_are_rope_rotated=False,
            rope_digest=rdigest,
            stores_pre_rope_keys=True,
            strategy=strategy.value,
        )
        attention[layer] = FullAttentionLayerArtifact(layer, k.copy(), v.copy(), pos.copy(), meta)
        relocation[layer] = meta
        if c.boundary_hidden is not None:
            anchors.original_hidden[layer] = np.asarray(c.boundary_hidden).copy()

    source_digest = "sha256:" + hashlib.sha256(json.dumps(source_tokens, separators=(",", ":")).encode()).hexdigest()
    art = ExecutionArtifact(
        source_segment_id=source_segment_id,
        identity=identity,
        fixed_seam_width=seam,
        recurrent=recurrent,
        source_token_digest=source_digest,
        boundary=anchors,
        conv_boundaries=conv,
        conv_decode_states=conv_decode,
        attention_relocation=relocation,
        attention=attention,
        capture_manifest_digest=capture.manifest.digest,
        position_metadata={
            "source_token_count": token_count,
            "stores_pre_rope_keys": True,
            "attention_position_strategies": {str(layer): meta.strategy for layer, meta in relocation.items()},
        },
    )
    art.recompute_byte_size()
    art.validate()
    return art
