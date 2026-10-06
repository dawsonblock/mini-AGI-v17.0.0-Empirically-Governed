from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .instrumentation import HybridCaptureManifest
from .layout import HybridLayerKind
from .live_session import CaptureEvent, LiveHybridCaptureSession


@dataclass(frozen=True)
class TransformersAdapterContract:
    """Version-pinned adapter metadata for upstream Transformers integration."""
    adapter_name: str
    transformers_version: str
    model_class: str
    capture_manifest_digest: str


class TransformersCaptureAdapter:
    """Stable wrapper around version-specific Qwen tensor extractors.

    Extractors receive ``(layer_module, args, kwargs, output)`` and must return
    the exact named payload required by ``LiveHybridCaptureSession``. RC10 never
    guesses tensor meaning from positional tuple indexes. A production adapter is
    therefore explicit, testable and tied to one upstream Transformers version.
    """
    def __init__(
        self,
        manifest: HybridCaptureManifest,
        *,
        contract: TransformersAdapterContract,
        gdn_extractors: Mapping[int, Callable[..., dict[str, Any]]],
        attention_extractors: Mapping[int, Callable[..., dict[str, Any]]],
    ):
        if contract.capture_manifest_digest != manifest.digest:
            raise ValueError("adapter contract capture manifest mismatch")
        self.manifest = manifest
        self.contract = contract
        self.gdn_extractors = dict(gdn_extractors)
        self.attention_extractors = dict(attention_extractors)
        expected_gdn = set(manifest.required_gdn_layers())
        expected_attn = set(manifest.required_attention_layers())
        if set(self.gdn_extractors) != expected_gdn:
            raise ValueError("GDN extractor layer set does not match capture manifest")
        if set(self.attention_extractors) != expected_attn:
            raise ValueError("attention extractor layer set does not match capture manifest")

    def capture_from_observations(self, observations: Mapping[int, tuple[Any, tuple[Any, ...], dict[str, Any], Any]]):
        session = LiveHybridCaptureSession(self.manifest)
        for req in self.manifest.requirements:
            if req.kind == HybridLayerKind.OTHER:
                continue
            if req.layer not in observations:
                raise RuntimeError(f"no live observation for layer {req.layer}")
            module, args, kwargs, output = observations[req.layer]
            extractor = self.gdn_extractors[req.layer] if req.kind == HybridLayerKind.GATED_DELTA else self.attention_extractors[req.layer]
            payload = extractor(module, args, kwargs, output)
            if not isinstance(payload, dict):
                raise TypeError("capture extractor must return a dict payload")
            session.record(CaptureEvent(req.layer, req.kind, payload))
        return session.finalize()
