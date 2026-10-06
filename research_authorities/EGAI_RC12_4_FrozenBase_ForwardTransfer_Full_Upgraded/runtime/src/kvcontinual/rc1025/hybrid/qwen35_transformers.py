from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from .instrumentation import HybridCaptureManifest
from .layout import HybridLayerKind
from .live_session import CaptureEvent, LiveHybridCaptureSession
from kvcontinual.rc1025.recurrent.hypic_capture import KeyHeadMapping


@dataclass(frozen=True)
class Qwen35StructuralContract:
    """Structural contract for current Hugging Face Qwen3.5 text modules.

    This intentionally checks attributes rather than trusting a class-name match.
    If upstream Transformers changes the computation, capture fails closed until
    this adapter is re-qualified.
    """
    adapter_name: str = "hf-qwen3.5-text-structural-v1"
    key_head_mapping: KeyHeadMapping = KeyHeadMapping.QWEN_REPEAT_INTERLEAVE
    qk_l2norm_eps: float = 1e-6


def _as_hidden(args: tuple[Any, ...], kwargs: dict[str, Any]):
    if "hidden_states" in kwargs:
        return kwargs["hidden_states"]
    if args:
        return args[0]
    raise RuntimeError("Qwen3.5 capture hook received no hidden_states")


def _token_major_cpu(x) -> np.ndarray:
    return x.detach().to(dtype=x.new_zeros(()).float().dtype).cpu().numpy()


def _mask_hidden(hidden, attention_mask):
    if attention_mask is None:
        return hidden
    if getattr(attention_mask, "ndim", None) != 2:
        raise RuntimeError("Qwen3.5 GDN capture expects the model's 2-D token mask")
    return hidden * attention_mask[:, :, None].to(dtype=hidden.dtype)


def _l2norm(x, eps: float):
    import torch
    return x.float() * torch.rsqrt((x.float() * x.float()).sum(dim=-1, keepdim=True) + eps)


def _apply_activation(x, activation: str | None):
    import torch.nn.functional as F
    if activation is None:
        return x
    if activation in ("silu", "swish"):
        return F.silu(x)
    raise RuntimeError(f"unsupported Qwen3.5 conv activation for capture adapter: {activation}")


def extract_qwen35_gdn_payload(module: Any, args: tuple[Any, ...], kwargs: dict[str, Any], *, seam_width: int) -> dict[str, Any]:
    """Reconstruct the exact fixed-input GDN tensors from a live layer input.

    The hook runs on the actual hidden state entering the GDN module. It reruns
    only local projections + the layer's causal depthwise convolution to expose
    tensors that upstream ``forward`` does not return. This does not alter the
    model output and is deliberately slower than a future native capture shim.
    """
    import torch
    import torch.nn.functional as F

    required = (
        "in_proj_qkv", "in_proj_b", "in_proj_a", "conv1d", "A_log", "dt_bias",
        "key_dim", "value_dim", "head_k_dim", "head_v_dim", "num_k_heads", "num_v_heads",
    )
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise RuntimeError(f"Qwen3.5 GDN structural contract mismatch: missing {missing}")

    hidden = _as_hidden(args, kwargs)
    if hidden.ndim != 3 or hidden.shape[0] != 1:
        raise RuntimeError("RC10.18 live capture currently requires batch_size=1")
    hidden = _mask_hidden(hidden, kwargs.get("attention_mask"))
    batch, seq_len, _ = hidden.shape
    if seq_len <= seam_width:
        raise RuntimeError("segment must contain tokens beyond the fixed seam")

    with torch.no_grad():
        # Raw causal-convolution input. This, not the already-convolved tensor,
        # is the state that has to cross a segment boundary.
        mixed_raw = module.in_proj_qkv(hidden)  # [1,T,C]
        conv_input = mixed_raw[0]
        mixed = mixed_raw.transpose(1, 2)
        weight = module.conv1d.weight.squeeze(1)
        bias = module.conv1d.bias
        ksize = int(weight.shape[-1])
        mixed = F.conv1d(
            mixed.to(weight.dtype), weight.unsqueeze(1), bias,
            padding=ksize - 1, groups=weight.shape[0],
        )[:, :, :seq_len]
        mixed = _apply_activation(mixed, getattr(module, "activation", "silu"))
        mixed = mixed.transpose(1, 2).to(hidden.dtype)

        query, key, value = torch.split(
            mixed, [int(module.key_dim), int(module.key_dim), int(module.value_dim)], dim=-1
        )
        key = key.reshape(batch, seq_len, int(module.num_k_heads), int(module.head_k_dim))
        value = value.reshape(batch, seq_len, int(module.num_v_heads), int(module.head_v_dim))
        # HF Qwen3.5 sets use_qk_l2norm_in_kernel=True, so the HYPIC transition
        # must be built from the normalized key vectors actually seen by GDN.
        key = _l2norm(key, 1e-6)

        b = module.in_proj_b(hidden)
        a = module.in_proj_a(hidden)
        beta = b.sigmoid().float()
        log_decay = -module.A_log.float().exp() * F.softplus(a.float() + module.dt_bias.float())
        decay = torch.exp(log_decay)

        channels = int(conv_input.shape[-1])
        incoming = torch.zeros((channels, max(0, ksize - 1)), dtype=conv_input.dtype, device=conv_input.device)
        boundary_hidden = hidden[0, :seam_width]

    return {
        "k": key[0].detach().float().cpu().numpy(),
        "v": value[0].detach().float().cpu().numpy(),
        "decay": decay[0].detach().float().cpu().numpy(),
        "beta": beta[0].detach().float().cpu().numpy(),
        "conv_input": conv_input.detach().float().cpu().numpy(),
        "incoming_conv_history": incoming.detach().float().cpu().numpy(),
        "boundary_hidden": boundary_hidden.detach().float().cpu().numpy(),
        "key_head_mapping": KeyHeadMapping.QWEN_REPEAT_INTERLEAVE,
    }


def extract_qwen35_attention_payload(
    module: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    seam_width: int,
    source_position_start: int = 0,
) -> dict[str, Any]:
    """Capture pre-RoPE K/V from the actual hidden input to a Qwen3.5 attention layer."""
    import torch

    required = ("k_proj", "v_proj", "k_norm", "head_dim")
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise RuntimeError(f"Qwen3.5 attention structural contract mismatch: missing {missing}")
    hidden = _as_hidden(args, kwargs)
    if hidden.ndim != 3 or hidden.shape[0] != 1:
        raise RuntimeError("RC10.18 live capture currently requires batch_size=1")
    batch, seq_len, _ = hidden.shape
    if seq_len <= seam_width:
        raise RuntimeError("segment must contain tokens beyond the fixed seam")
    with torch.no_grad():
        shape = (*hidden.shape[:-1], -1, int(module.head_dim))
        key = module.k_norm(module.k_proj(hidden).view(shape))
        value = module.v_proj(hidden).view(shape)
        positions = torch.arange(source_position_start, source_position_start + seq_len, device=hidden.device, dtype=torch.long)
        boundary_hidden = hidden[0, :seam_width]
    return {
        "pre_rope_keys": key[0].detach().float().cpu().numpy(),
        "values": value[0].detach().float().cpu().numpy(),
        "source_positions": positions.detach().cpu().numpy(),
        "boundary_hidden": boundary_hidden.detach().float().cpu().numpy(),
    }


def discover_qwen35_capture_modules(model: Any, manifest: HybridCaptureManifest) -> dict[int, Any]:
    """Find exact GDN/attention modules by ``layer_idx`` and structural kind."""
    wanted = {r.layer: r.kind for r in manifest.requirements if r.kind != HybridLayerKind.OTHER}
    found: dict[int, Any] = {}
    for _name, module in model.named_modules():
        layer = getattr(module, "layer_idx", None)
        if layer is None or int(layer) not in wanted:
            continue
        layer = int(layer)
        kind = wanted[layer]
        class_name = module.__class__.__name__.lower()
        if kind == HybridLayerKind.GATED_DELTA:
            looks_right = "gateddeltanet" in class_name or all(hasattr(module, x) for x in ("in_proj_qkv", "A_log", "dt_bias", "conv1d"))
        else:
            looks_right = "attention" in class_name or all(hasattr(module, x) for x in ("k_proj", "v_proj", "k_norm"))
        if looks_right:
            if layer in found and found[layer] is not module:
                raise RuntimeError(f"multiple candidate Qwen3.5 capture modules for layer {layer}")
            found[layer] = module
    missing = sorted(set(wanted) - set(found))
    if missing:
        raise RuntimeError(f"Qwen3.5 model does not satisfy capture manifest; missing layers {missing}")
    return found


class Qwen35TransformersLiveCapture:
    """Current-Transformers structural capture adapter for text-only Qwen3.5/3.6.

    It is intentionally a qualification adapter, not a performance path: local
    projections are recomputed inside pre-hooks to expose otherwise-hidden GDN
    tensors. A future optimized adapter can replace this without changing the
    persistent capture ABI.
    """

    def __init__(self, model: Any, manifest: HybridCaptureManifest, *, source_position_start: int = 0):
        self.model = model
        self.manifest = manifest
        self.source_position_start = int(source_position_start)
        self.modules = discover_qwen35_capture_modules(model, manifest)
        self.session = LiveHybridCaptureSession(manifest)
        self._handles: list[Any] = []

    def _hook_for(self, layer: int, kind: HybridLayerKind):
        seam = int(self.manifest.seam_width)
        def hook(module, args, kwargs):
            if kind == HybridLayerKind.GATED_DELTA:
                payload = extract_qwen35_gdn_payload(module, args, kwargs, seam_width=seam)
            else:
                payload = extract_qwen35_attention_payload(
                    module, args, kwargs, seam_width=seam, source_position_start=self.source_position_start
                )
            self.session.record(CaptureEvent(layer, kind, payload))
        return hook

    def install(self) -> None:
        if self._handles:
            raise RuntimeError("Qwen3.5 capture hooks already installed")
        req_by_layer = {r.layer: r for r in self.manifest.requirements}
        for layer, module in sorted(self.modules.items()):
            req = req_by_layer[layer]
            self._handles.append(module.register_forward_pre_hook(self._hook_for(layer, req.kind), with_kwargs=True))

    def remove(self) -> None:
        while self._handles:
            self._handles.pop().remove()

    def finalize(self):
        return self.session.finalize()

    def capture_prefill(self, *, input_ids, **model_kwargs):
        import torch
        self.install()
        try:
            with torch.inference_mode():
                output = self.model(input_ids=input_ids, use_cache=False, **model_kwargs)
            return self.finalize(), output
        finally:
            self.remove()
