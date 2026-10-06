from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Callable, Mapping

import numpy as np

from kvcontinual.rc1025.attention.relocation import AttentionRelocationStrategy, FullAttentionRelocationMetadata, rope_apply
from kvcontinual.rc1025.cache.block import ExecutionArtifact
from kvcontinual.rc1025.hybrid.seam_plan import SeamFirstSegmentPlan
from kvcontinual.rc1025.hybrid.state_plane import HybridExecutionState
from kvcontinual.rc1025.recurrent.conv_boundary import ConvBoundaryState, ConvDecodeState


PositionReapply = Callable[[int, np.ndarray, np.ndarray, FullAttentionRelocationMetadata], np.ndarray]


def _digest_payload(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class TailInjectionReceipt:
    """Tamper-evident proof of one cached-tail state transition.

    Unlike the segment schedule receipt, this receipt binds the *state-plane
    transition*: exact artifact content, execution identity, position range,
    before/after state digests, and the recurrent/conv/attention planes touched.
    It still does not claim model-level quality; exact-replay qualification is a
    separate gate.
    """

    source_segment_id: str
    source_token_digest: str
    artifact_content_digest: str
    execution_identity_digest: str
    new_position_start: int
    new_position_end: int
    before_state_digest: str
    after_state_digest: str
    recurrent_keys: tuple[str, ...]
    conv_layers: tuple[int, ...]
    conv_decode_layers: tuple[int, ...]
    attention_layers: tuple[int, ...]
    created_at: str
    receipt_digest: str = ""

    def unsigned_payload(self) -> dict:
        out = asdict(self)
        out.pop("receipt_digest", None)
        return out

    def expected_digest(self) -> str:
        return _digest_payload(self.unsigned_payload())

    @property
    def valid_digest(self) -> bool:
        return bool(self.receipt_digest) and self.receipt_digest == self.expected_digest()




def build_tail_injection_receipt(
    artifact: ExecutionArtifact,
    step: SeamFirstSegmentPlan,
    *,
    before_state_digest: str,
    after_state_digest: str,
) -> TailInjectionReceipt:
    if artifact.source_segment_id != step.source_segment_id:
        raise ValueError("tail receipt artifact/source mismatch")
    if artifact.source_token_digest != step.source_token_digest:
        raise ValueError("tail receipt source-token digest mismatch")
    if artifact.content_digest != step.artifact_content_digest:
        raise ValueError("tail receipt artifact digest mismatch")
    if artifact.identity.digest != step.execution_identity_digest:
        raise ValueError("tail receipt execution identity mismatch")
    if not before_state_digest.startswith("sha256:") or not after_state_digest.startswith("sha256:"):
        raise ValueError("tail receipt state digests must be sha256 digests")
    receipt = TailInjectionReceipt(
        source_segment_id=step.source_segment_id,
        source_token_digest=step.source_token_digest,
        artifact_content_digest=step.artifact_content_digest,
        execution_identity_digest=step.execution_identity_digest,
        new_position_start=step.new_position_start + step.seam_width,
        new_position_end=step.new_position_end,
        before_state_digest=before_state_digest,
        after_state_digest=after_state_digest,
        recurrent_keys=tuple(f"{layer}:{head}" for layer, head in sorted(artifact.recurrent)),
        conv_layers=tuple(sorted(artifact.conv_boundaries)),
        conv_decode_layers=tuple(sorted(artifact.conv_decode_states)),
        attention_layers=tuple(sorted(artifact.attention)),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return replace(receipt, receipt_digest=receipt.expected_digest())


def _copy_conv(state: ConvBoundaryState) -> ConvBoundaryState:
    return ConvBoundaryState(np.asarray(state.history).copy(), int(state.kernel_size))




def _copy_conv_decode(state: ConvDecodeState) -> ConvDecodeState:
    return ConvDecodeState(np.asarray(state.history).copy(), int(state.kernel_size))


def _relocate_tail_keys(
    layer: int,
    pre_rope_keys: np.ndarray,
    new_positions: np.ndarray,
    meta: FullAttentionRelocationMetadata,
    *,
    model_position_reapply: PositionReapply | None,
    rope_inv_freq_by_layer: Mapping[int, np.ndarray] | None,
) -> np.ndarray:
    strategy = AttentionRelocationStrategy(meta.strategy)
    if strategy == AttentionRelocationStrategy.MODEL_REAPPLY_PRE_ROPE:
        if model_position_reapply is None:
            raise ValueError(f"layer {layer}: model-native position reapply callback is required")
        out = np.asarray(model_position_reapply(layer, pre_rope_keys, new_positions, meta))
    elif strategy == AttentionRelocationStrategy.PAIRWISE_ROPE_DELTA:
        if rope_inv_freq_by_layer is None or layer not in rope_inv_freq_by_layer:
            raise ValueError(f"layer {layer}: inv_freq is required for pairwise RoPE relocation")
        out = rope_apply(pre_rope_keys, new_positions, np.asarray(rope_inv_freq_by_layer[layer]))
    else:  # pragma: no cover - Enum conversion currently prevents this branch.
        raise ValueError(f"unsupported attention relocation strategy: {meta.strategy}")
    if out.shape != np.asarray(pre_rope_keys).shape:
        raise ValueError(f"layer {layer}: relocated key shape changed")
    return out


def inject_cached_tail(
    state: HybridExecutionState,
    artifact: ExecutionArtifact,
    step: SeamFirstSegmentPlan,
    *,
    model_position_reapply: PositionReapply | None = None,
    rope_inv_freq_by_layer: Mapping[int, np.ndarray] | None = None,
) -> TailInjectionReceipt:
    """Apply only ``source_tokens[seam_width:]`` to already-fresh seam state.

    This is a correctness/reference implementation for native backend bring-up.
    It proves that the recurrent state, outgoing convolution history and full-
    attention tail are all updated from the exact artifact described by the seam
    plan, without reprocessing the seam or silently retaining old positions.
    """

    state.validate()
    artifact.validate()
    if artifact.source_segment_id != step.source_segment_id:
        raise ValueError("tail injection artifact/source mismatch")
    if artifact.source_token_digest != step.source_token_digest:
        raise ValueError("tail injection source-token digest mismatch")
    if artifact.content_digest != step.artifact_content_digest:
        raise ValueError("tail injection artifact digest mismatch")
    if artifact.identity.digest != step.execution_identity_digest:
        raise ValueError("tail injection artifact execution identity mismatch")
    if state.execution_identity_digest != step.execution_identity_digest:
        raise ValueError("tail injection state execution identity mismatch")
    if artifact.fixed_seam_width != step.seam_width:
        raise ValueError("tail injection seam-width mismatch")

    expected_before = step.new_position_start + step.seam_width
    if state.token_count != expected_before:
        raise ValueError(
            f"cached tail may run only after the fresh seam: state token_count={state.token_count}, expected={expected_before}"
        )

    before = state.digest

    # Recurrent plane: every cached tail acts on the freshly reconstructed state.
    for key in sorted(artifact.recurrent):
        if key not in state.recurrent:
            raise ValueError(f"missing fresh recurrent state for layer/head {key}")
        item = artifact.recurrent[key]
        state.recurrent[key] = item.tail_summary.apply(np.asarray(state.recurrent[key]))

    # Convolution plane: once the cached tail is accepted, its original raw
    # projected tail is also the trajectory being reused, so the outgoing raw
    # projection history becomes the artifact's outgoing history.
    for layer, boundary in artifact.conv_boundaries.items():
        state.conv[layer] = _copy_conv(boundary)

    for layer, decode_state in artifact.conv_decode_states.items():
        state.conv_decode[layer] = _copy_conv_decode(decode_state)

    # Attention plane: the seam is already present in the new context. Append only
    # cached tail K/V, and reapply positions under the new assembled locations.
    for layer, attn in sorted(artifact.attention.items()):
        if layer not in state.attention:
            raise ValueError(f"missing fresh attention seam cache for layer {layer}")
        seam = step.seam_width
        tail_k = np.asarray(attn.pre_rope_keys)[seam:]
        tail_v = np.asarray(attn.values)[seam:]
        new_pos = np.arange(step.new_position_start + seam, step.new_position_end, dtype=np.int64)
        if tail_k.shape[0] != step.tail_token_count or tail_v.shape[0] != step.tail_token_count:
            raise ValueError(f"layer {layer}: cached attention tail length disagrees with seam plan")
        relocated = _relocate_tail_keys(
            layer,
            tail_k,
            new_pos,
            attn.relocation,
            model_position_reapply=model_position_reapply,
            rope_inv_freq_by_layer=rope_inv_freq_by_layer,
        )
        state.attention[layer].append(relocated, tail_v, new_pos)

    state.token_count = step.new_position_end
    state.validate()
    after = state.digest
    return build_tail_injection_receipt(
        artifact,
        step,
        before_state_digest=before,
        after_state_digest=after,
    )


def validate_tail_injection_receipt(
    receipt: TailInjectionReceipt,
    artifact: ExecutionArtifact,
    step: SeamFirstSegmentPlan,
    *,
    expected_before_state_digest: str | None = None,
    expected_after_state_digest: str | None = None,
) -> None:
    if not receipt.valid_digest:
        raise ValueError("tail injection receipt digest is invalid")
    if receipt.source_segment_id != step.source_segment_id or receipt.source_segment_id != artifact.source_segment_id:
        raise ValueError("tail injection receipt source mismatch")
    if receipt.source_token_digest != step.source_token_digest or receipt.source_token_digest != artifact.source_token_digest:
        raise ValueError("tail injection receipt source-token digest mismatch")
    if receipt.artifact_content_digest != step.artifact_content_digest or receipt.artifact_content_digest != artifact.content_digest:
        raise ValueError("tail injection receipt artifact digest mismatch")
    if receipt.execution_identity_digest != step.execution_identity_digest or receipt.execution_identity_digest != artifact.identity.digest:
        raise ValueError("tail injection receipt execution identity mismatch")
    if receipt.new_position_start != step.new_position_start + step.seam_width or receipt.new_position_end != step.new_position_end:
        raise ValueError("tail injection receipt position range mismatch")
    if receipt.recurrent_keys != tuple(f"{l}:{h}" for l, h in sorted(artifact.recurrent)):
        raise ValueError("tail injection receipt recurrent-plane mismatch")
    if receipt.conv_layers != tuple(sorted(artifact.conv_boundaries)):
        raise ValueError("tail injection receipt convolution-plane mismatch")
    if receipt.conv_decode_layers != tuple(sorted(artifact.conv_decode_states)):
        raise ValueError("tail injection receipt convolution-decode-plane mismatch")
    if receipt.attention_layers != tuple(sorted(artifact.attention)):
        raise ValueError("tail injection receipt attention-plane mismatch")
    if expected_before_state_digest is not None and receipt.before_state_digest != expected_before_state_digest:
        raise ValueError("tail injection receipt before-state mismatch")
    if expected_after_state_digest is not None and receipt.after_state_digest != expected_after_state_digest:
        raise ValueError("tail injection receipt after-state mismatch")
