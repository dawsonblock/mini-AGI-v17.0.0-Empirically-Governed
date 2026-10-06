from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capture_buffer import AttentionLayerCapture, GdnLayerCapture, HybridCaptureBuffer
from .instrumentation import HybridCaptureManifest
from .layout import HybridLayerKind
from kvcontinual.rc1025.recurrent.hypic_capture import KeyHeadMapping


@dataclass(frozen=True)
class CaptureEvent:
    layer: int
    kind: HybridLayerKind
    payload: dict[str, Any]


class LiveHybridCaptureSession:
    """Fail-closed event sink for a real Qwen/Transformers instrumentation shim."""
    def __init__(self, manifest: HybridCaptureManifest):
        self.buffer = HybridCaptureBuffer(manifest)
        self._seen: set[int] = set()

    @property
    def manifest(self) -> HybridCaptureManifest:
        return self.buffer.manifest

    def record(self, event: CaptureEvent) -> None:
        if event.layer in self._seen:
            raise ValueError(f"duplicate live capture event for layer {event.layer}")
        req = next((r for r in self.manifest.requirements if r.layer == event.layer), None)
        if req is None:
            raise KeyError(f"layer {event.layer} is not in capture manifest")
        if req.kind != event.kind:
            raise ValueError(f"layer {event.layer} expected {req.kind.value}, got {event.kind.value}")

        p = event.payload
        if event.kind == HybridLayerKind.GATED_DELTA:
            conv_key = "conv_input" if "conv_input" in p else "conv_projected" if "conv_projected" in p else None
            needed = ("k", "v", "decay", "beta", "incoming_conv_history")
            missing = [x for x in needed if x not in p]
            if conv_key is None:
                missing.append("conv_input")
            if missing:
                raise ValueError(f"layer {event.layer}: missing GDN fields {missing}")
            mapping = p.get("key_head_mapping", KeyHeadMapping.QWEN_REPEAT_INTERLEAVE)
            if not isinstance(mapping, KeyHeadMapping):
                mapping = KeyHeadMapping(str(mapping))
            self.buffer.put_gdn(event.layer, GdnLayerCapture(
                p["k"], p["v"], p["decay"], p["beta"], p[conv_key],
                p["incoming_conv_history"], p.get("boundary_hidden"), mapping,
            ))
        elif event.kind == HybridLayerKind.FULL_ATTENTION:
            needed = ("pre_rope_keys", "values", "source_positions")
            missing = [x for x in needed if x not in p]
            if missing:
                raise ValueError(f"layer {event.layer}: missing attention fields {missing}")
            self.buffer.put_attention(event.layer, AttentionLayerCapture(
                p["pre_rope_keys"], p["values"], p["source_positions"], p.get("boundary_hidden")
            ))
        else:
            raise ValueError("OTHER layers are not cache-capture events")
        self._seen.add(event.layer)

    def finalize(self) -> HybridCaptureBuffer:
        missing = self.buffer.missing_requirements()
        if missing:
            raise RuntimeError("live capture incomplete: " + ", ".join(missing))
        return self.buffer
