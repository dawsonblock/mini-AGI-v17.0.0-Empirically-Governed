from .layout import HybridLayerKind, HybridLayerSpec, HybridModelLayout
from .instrumentation import CaptureRequirement, HybridCaptureManifest, build_capture_manifest
from .capture_buffer import AttentionLayerCapture, GdnLayerCapture, HybridCaptureBuffer
from .live_session import CaptureEvent, LiveHybridCaptureSession
from .materialize import MaterializationInputs, materialize_execution_artifact
from .seam_plan import SeamFirstAssemblyPlan, SeamFirstSegmentPlan, build_seam_first_plan
from .transformers_adapter import TransformersAdapterContract, TransformersCaptureAdapter

__all__ = [
    "HybridLayerKind", "HybridLayerSpec", "HybridModelLayout",
    "CaptureRequirement", "HybridCaptureManifest", "build_capture_manifest",
    "AttentionLayerCapture", "GdnLayerCapture", "HybridCaptureBuffer",
    "CaptureEvent", "LiveHybridCaptureSession",
    "MaterializationInputs", "materialize_execution_artifact",
    "SeamFirstAssemblyPlan", "SeamFirstSegmentPlan", "build_seam_first_plan",
    "TransformersAdapterContract", "TransformersCaptureAdapter",
]

from .qwen35_transformers import (
    Qwen35StructuralContract,
    Qwen35TransformersLiveCapture,
    discover_qwen35_capture_modules,
    extract_qwen35_attention_payload,
    extract_qwen35_gdn_payload,
)

from .seam_execution import SeamExecutionEvent, SeamExecutionTrace, SeamPhase
