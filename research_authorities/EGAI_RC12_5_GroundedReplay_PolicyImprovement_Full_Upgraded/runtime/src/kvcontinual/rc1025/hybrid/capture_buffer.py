from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .instrumentation import HybridCaptureManifest
from .layout import HybridLayerKind
from kvcontinual.rc1025.recurrent.hypic_capture import KeyHeadMapping


@dataclass
class GdnLayerCapture:
    k: Any
    v: Any
    decay: Any
    beta: Any
    # Raw token-major input to the depthwise causal convolution [T,C]. This is
    # the state that must be carried across a new segment boundary.
    conv_input: Any
    # Diagnostic only: state that preceded this independently captured segment.
    incoming_conv_history: Any
    boundary_hidden: Any | None = None
    key_head_mapping: KeyHeadMapping = KeyHeadMapping.QWEN_REPEAT_INTERLEAVE

    @property
    def conv_projected(self) -> Any:
        """RC10.17 compatibility alias. The old name was semantically vague."""
        return self.conv_input


@dataclass
class AttentionLayerCapture:
    pre_rope_keys: Any
    values: Any
    source_positions: Any
    boundary_hidden: Any | None = None


@dataclass
class HybridCaptureBuffer:
    """Version-agnostic capture boundary for real Qwen/Transformers hooks."""
    manifest: HybridCaptureManifest
    gdn: dict[int, GdnLayerCapture] = field(default_factory=dict)
    attention: dict[int, AttentionLayerCapture] = field(default_factory=dict)

    def put_gdn(self, layer: int, capture: GdnLayerCapture) -> None:
        self._require_kind(layer, HybridLayerKind.GATED_DELTA)
        self.gdn[layer] = capture

    def put_attention(self, layer: int, capture: AttentionLayerCapture) -> None:
        self._require_kind(layer, HybridLayerKind.FULL_ATTENTION)
        self.attention[layer] = capture

    def _require_kind(self, layer: int, kind: HybridLayerKind) -> None:
        matches = [r for r in self.manifest.requirements if r.layer == layer]
        if not matches:
            raise KeyError(f"layer {layer} is not in capture manifest")
        if matches[0].kind != kind:
            raise ValueError(f"layer {layer} is {matches[0].kind.value}, not {kind.value}")


    @property
    def complete(self) -> bool:
        return not self.missing_requirements()

    def missing_requirements(self) -> list[str]:
        missing: list[str] = []
        for req in self.manifest.requirements:
            if req.kind == HybridLayerKind.GATED_DELTA and req.layer not in self.gdn:
                missing.append(f"layer {req.layer}:gdn")
            elif req.kind == HybridLayerKind.FULL_ATTENTION and req.layer not in self.attention:
                missing.append(f"layer {req.layer}:attention")
        return missing
