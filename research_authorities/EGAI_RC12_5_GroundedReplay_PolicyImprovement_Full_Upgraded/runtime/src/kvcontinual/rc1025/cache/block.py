from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import uuid
import numpy as np

from kvcontinual.rc1025.attention.relocation import FullAttentionRelocationMetadata
from kvcontinual.rc1025.recurrent.affine import AffineSummary
from kvcontinual.rc1025.recurrent.conv_boundary import ConvBoundaryState, ConvDecodeState
from kvcontinual.rc1025.types import CacheTier, ExecutionIdentity


def _hash_array(h: "hashlib._Hash", value: Any) -> None:
    a = np.ascontiguousarray(value)
    h.update(str(a.dtype).encode())
    h.update(json.dumps(list(a.shape), separators=(",", ":")).encode())
    h.update(a.tobytes())


@dataclass
class BoundaryAnchors:
    """Original boundary observations used only as comparison anchors.

    Fresh seam values are always computed under the new predecessor; these anchors
    are never treated as authoritative after relocation.
    """
    leading_tokens: list[int] = field(default_factory=list)
    original_hidden: dict[int, np.ndarray] = field(default_factory=dict)
    original_attention_output: dict[int, np.ndarray] = field(default_factory=dict)
    original_route_ids: dict[int, np.ndarray] = field(default_factory=dict)


@dataclass
class RecurrentTailArtifact:
    layer: int
    head: int
    seam_width: int
    # This summary represents source_tokens[seam_width:] ONLY.
    tail_summary: AffineSummary
    trailing_conv_payload: np.ndarray | None = None
    stats: dict[str, float] = field(default_factory=dict)
    # Exact key-head association used to construct this value-head summary.
    key_head: int | None = None
    key_head_mapping: str = "legacy_unspecified"


@dataclass
class FullAttentionLayerArtifact:
    """Concrete full-attention payload for one reusable segment/layer.

    RC10.16 still allowed an opaque ``attention_kv_ref``. RC10.17 keeps that
    legacy field for migration but makes the authoritative reference artifact
    explicit: pre-RoPE keys, values, source positions and relocation metadata.
    Production backends may replace the NumPy arrays with native storage handles
    after preserving the same digest/shape contract.
    """
    layer: int
    pre_rope_keys: np.ndarray
    values: np.ndarray
    source_positions: np.ndarray
    relocation: FullAttentionRelocationMetadata

    def validate(self) -> None:
        k = np.asarray(self.pre_rope_keys)
        v = np.asarray(self.values)
        p = np.asarray(self.source_positions)
        if self.layer != self.relocation.layer:
            raise ValueError("attention artifact layer/relocation layer mismatch")
        if k.ndim < 2 or v.ndim < 2 or k.shape[0] != v.shape[0]:
            raise ValueError("attention keys/values must be token-major with matching token count")
        if p.ndim != 1 or p.shape[0] != k.shape[0]:
            raise ValueError("source_positions must have one value per cached token")
        if self.relocation.token_count != k.shape[0]:
            raise ValueError("relocation token_count does not match attention payload")
        self.relocation.validate()

    @property
    def byte_size(self) -> int:
        return int(np.asarray(self.pre_rope_keys).nbytes + np.asarray(self.values).nbytes + np.asarray(self.source_positions).nbytes)


@dataclass(frozen=True)
class ArtifactQualification:
    """Tamper-evident evidence that a derived artifact may use HYPIC reuse."""
    same_hidden_input_verified: bool = False
    conv_boundary_complete: bool = False
    attention_relocation_complete: bool = False
    oracle_qualified: bool = False
    max_logit_kl: float = float("inf")
    min_top1_agreement: float = 0.0
    hardware_fingerprint: str = ""
    capture_manifest_digest: str = ""
    receipt_digest: str = ""
    execution_identity_digest: str = ""
    artifact_content_digest: str = ""
    evidence_digest: str = ""

    def expected_receipt_digest(self) -> str:
        payload = {
            "same_hidden_input_verified": self.same_hidden_input_verified,
            "conv_boundary_complete": self.conv_boundary_complete,
            "attention_relocation_complete": self.attention_relocation_complete,
            "oracle_qualified": self.oracle_qualified,
            "max_logit_kl": float(self.max_logit_kl),
            "min_top1_agreement": float(self.min_top1_agreement),
            "hardware_fingerprint": self.hardware_fingerprint,
            "capture_manifest_digest": self.capture_manifest_digest,
            "execution_identity_digest": self.execution_identity_digest,
            "artifact_content_digest": self.artifact_content_digest,
            "evidence_digest": self.evidence_digest,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    @property
    def reusable_for_hypic(self) -> bool:
        return (
            self.same_hidden_input_verified
            and self.conv_boundary_complete
            and self.attention_relocation_complete
            and self.oracle_qualified
            and bool(self.hardware_fingerprint)
            and bool(self.capture_manifest_digest)
            and bool(self.execution_identity_digest)
            and bool(self.artifact_content_digest)
            and bool(self.evidence_digest)
            and bool(self.receipt_digest)
            and self.receipt_digest == self.expected_receipt_digest()
        )


@dataclass
class ExecutionArtifact:
    source_segment_id: str
    identity: ExecutionIdentity
    fixed_seam_width: int
    recurrent: dict[tuple[int, int], RecurrentTailArtifact]
    # Digest of the authoritative source tokens used to compile this artifact.
    # Empty is accepted only for legacy/in-memory research fixtures; production
    # reuse is fail-closed in ReconstructionRuntime when this binding is absent.
    source_token_digest: str = ""
    attention_kv_ref: str | None = None
    position_metadata: dict[str, Any] = field(default_factory=dict)
    boundary: BoundaryAnchors = field(default_factory=BoundaryAnchors)
    conv_boundaries: dict[int, ConvBoundaryState] = field(default_factory=dict)
    conv_decode_states: dict[int, ConvDecodeState] = field(default_factory=dict)
    attention_relocation: dict[int, FullAttentionRelocationMetadata] = field(default_factory=dict)
    attention: dict[int, FullAttentionLayerArtifact] = field(default_factory=dict)
    capture_manifest_digest: str = ""
    qualification: ArtifactQualification | None = None
    tier: CacheTier = CacheTier.DRAM
    byte_size: int = 0
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def content_digest(self) -> str:
        """Digest only authoritative model-derived content, never mutable tier metadata."""
        h = hashlib.sha256()
        h.update(self.source_segment_id.encode())
        h.update(self.source_token_digest.encode())
        h.update(self.identity.digest.encode())
        h.update(str(self.fixed_seam_width).encode())
        h.update(self.capture_manifest_digest.encode())
        for key in sorted(self.recurrent):
            r = self.recurrent[key]
            h.update(f"r:{r.layer}:{r.head}:{r.seam_width}:{r.key_head}:{r.key_head_mapping}".encode())
            _hash_array(h, r.tail_summary.T)
            _hash_array(h, r.tail_summary.Z)
            h.update(r.tail_summary.orientation.value.encode())
            if r.trailing_conv_payload is not None:
                _hash_array(h, r.trailing_conv_payload)
        for layer in sorted(self.conv_boundaries):
            c = self.conv_boundaries[layer]
            h.update(f"c:{layer}:{c.kernel_size}".encode())
            _hash_array(h, c.history)
        for layer in sorted(self.conv_decode_states):
            c = self.conv_decode_states[layer]
            h.update(f"cd:{layer}:{c.kernel_size}".encode())
            _hash_array(h, c.history)
        for layer in sorted(self.attention):
            a = self.attention[layer]
            h.update(f"a:{layer}".encode())
            _hash_array(h, a.pre_rope_keys)
            _hash_array(h, a.values)
            _hash_array(h, a.source_positions)
            h.update(json.dumps(asdict(a.relocation), sort_keys=True, separators=(",", ":")).encode())
        for layer in sorted(self.attention_relocation):
            if layer not in self.attention:
                h.update(f"ar:{layer}".encode())
                h.update(json.dumps(asdict(self.attention_relocation[layer]), sort_keys=True, separators=(",", ":")).encode())
        return "sha256:" + h.hexdigest()

    def recompute_byte_size(self) -> int:
        size = 0
        for r in self.recurrent.values():
            size += int(np.asarray(r.tail_summary.T).nbytes + np.asarray(r.tail_summary.Z).nbytes)
            if r.trailing_conv_payload is not None:
                size += int(np.asarray(r.trailing_conv_payload).nbytes)
        for c in self.conv_boundaries.values():
            size += int(np.asarray(c.history).nbytes)
        for c in self.conv_decode_states.values():
            size += int(np.asarray(c.history).nbytes)
        size += sum(a.byte_size for a in self.attention.values())
        self.byte_size = int(size)
        return self.byte_size

    def validate(self) -> None:
        if self.source_token_digest and not self.source_token_digest.startswith("sha256:"):
            raise ValueError("source_token_digest must be a sha256 digest")
        if self.fixed_seam_width < 0:
            raise ValueError("fixed_seam_width must be >= 0")
        for key, item in self.recurrent.items():
            if key != (item.layer, item.head):
                raise ValueError(f"recurrent key {key} does not match layer/head")
            if item.seam_width != self.fixed_seam_width:
                raise ValueError("all recurrent tails must share the artifact seam contract")
            if item.key_head is not None and item.key_head < 0:
                raise ValueError("recurrent key_head must be non-negative")
            if not item.key_head_mapping:
                raise ValueError("recurrent key_head_mapping is required")
        for layer, state in self.conv_boundaries.items():
            if layer < 0:
                raise ValueError("convolution layer index must be non-negative")
            state.validate()
        for layer, state in self.conv_decode_states.items():
            if layer < 0:
                raise ValueError("convolution decode layer index must be non-negative")
            state.validate()
            if layer in self.conv_boundaries and self.conv_boundaries[layer].kernel_size != state.kernel_size:
                raise ValueError("seam/decode convolution kernel sizes disagree")
        for layer, meta in self.attention_relocation.items():
            if layer != meta.layer:
                raise ValueError("attention relocation key must equal metadata layer")
            meta.validate()
        for layer, attn in self.attention.items():
            if layer != attn.layer:
                raise ValueError("attention artifact key must equal layer")
            attn.validate()
            if layer in self.attention_relocation and self.attention_relocation[layer] != attn.relocation:
                raise ValueError("attention payload relocation metadata mismatch")
        if self.qualification is not None:
            q = self.qualification
            if self.capture_manifest_digest and q.capture_manifest_digest != self.capture_manifest_digest:
                raise ValueError("qualification capture manifest does not match execution artifact")
            if q.execution_identity_digest != self.identity.digest:
                raise ValueError("qualification execution identity does not match artifact")
            if q.artifact_content_digest != self.content_digest:
                raise ValueError("qualification content digest does not match artifact")
            if q.receipt_digest != q.expected_receipt_digest():
                raise ValueError("qualification receipt digest is invalid")

    @property
    def hypic_qualified(self) -> bool:
        return bool(self.qualification is not None and self.qualification.reusable_for_hypic)


# Legacy wrapper retained so old tests/tools can still load an RC10 block. New
# code should use SourceSegment + ExecutionArtifact instead.
@dataclass
class HybridMemoryBlock:
    block_id: str
    token_start: int
    token_end: int
    tokens: list[int]
    recurrence: dict[int, AffineSummary]
    cache_identity: object
    position_metadata: dict[str, Any] = field(default_factory=dict)
    attention_kv_ref: str | None = None
    entry_hidden: dict[int, np.ndarray] = field(default_factory=dict)
    exit_hidden: dict[int, np.ndarray] = field(default_factory=dict)
    conv_boundary_state: dict[int, np.ndarray] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return self.token_end - self.token_start
