from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from kvcontinual.rc1025.attention.relocation import FullAttentionRelocationMetadata


def qwen35_text_position_ids(positions: np.ndarray) -> np.ndarray:
    """Build the 3-axis text position IDs expected by Qwen3.5 text RoPE.

    Pure text uses the same monotonically increasing coordinate for temporal,
    height and width axes. Multimodal relocation is deliberately not inferred
    here; callers must provide model-native multimodal coordinates instead.
    """
    p = np.asarray(positions, dtype=np.int64)
    if p.ndim != 1:
        raise ValueError("positions must be rank-1")
    if p.size and np.any(p < 0):
        raise ValueError("positions must be non-negative")
    return np.stack([p, p, p], axis=0)[:, None, :]


def _resolve_text_model(model: Any) -> Any:
    """Resolve the object owning Qwen3.5 text ``rotary_emb`` fail-closed."""
    seen: set[int] = set()
    queue = [model]
    while queue:
        obj = queue.pop(0)
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        if hasattr(obj, "rotary_emb") and hasattr(obj, "config"):
            return obj
        for name in ("model", "language_model", "text_model"):
            child = getattr(obj, name, None)
            if child is not None:
                queue.append(child)
    raise RuntimeError("could not resolve Qwen3.5 text model with rotary_emb")


@dataclass
class Qwen35TextPositionReapply:
    """Model-native Qwen3.5 text MRoPE reapplication bridge.

    The bridge consumes token-major pre-RoPE keys [T,H,D] from RC10 artifacts,
    invokes the deployed model's own rotary embedding object for the relocated
    positions, then calls the exact Transformers rotary application function.
    This keeps position semantics tied to the running model instead of cloning
    Qwen's MRoPE math into the cache layer.
    """

    rotary_emb: Any
    apply_rotary_pos_emb: Callable[..., Any]
    device: Any
    dtype: Any

    @classmethod
    def from_model(cls, model: Any) -> "Qwen35TextPositionReapply":
        import torch
        try:
            from transformers.models.qwen3_5.modeling_qwen3_5 import apply_rotary_pos_emb
        except Exception as exc:  # pragma: no cover - depends on optional Transformers install.
            raise RuntimeError("current Transformers Qwen3.5 rotary function is unavailable") from exc
        text_model = _resolve_text_model(model)
        rotary = text_model.rotary_emb
        param = next(model.parameters(), None)
        device = param.device if param is not None else torch.device("cpu")
        dtype = param.dtype if param is not None and getattr(param.dtype, "is_floating_point", False) else torch.float32
        return cls(rotary, apply_rotary_pos_emb, device, dtype)

    def __call__(
        self,
        layer: int,
        pre_rope_keys: np.ndarray,
        positions: np.ndarray,
        metadata: FullAttentionRelocationMetadata,
    ) -> np.ndarray:
        del layer  # RoPE is shared across text attention layers for one model identity.
        import torch

        k_np = np.asarray(pre_rope_keys)
        p_np = np.asarray(positions, dtype=np.int64)
        if k_np.ndim != 3:
            raise ValueError("Qwen3.5 pre-RoPE keys must be [tokens, kv_heads, head_dim]")
        if p_np.ndim != 1 or p_np.shape[0] != k_np.shape[0]:
            raise ValueError("Qwen3.5 position count must match cached key tokens")
        if not metadata.stores_pre_rope_keys or metadata.keys_are_rope_rotated:
            raise ValueError("Qwen3.5 model-native reapply requires pre-RoPE keys")

        # Qwen attention uses [B,H,T,D] internally.
        k = torch.as_tensor(k_np, device=self.device, dtype=self.dtype).permute(1, 0, 2).unsqueeze(0)
        q = torch.zeros_like(k)
        pos = torch.as_tensor(qwen35_text_position_ids(p_np), device=self.device, dtype=torch.long)
        # rotary_emb uses x only for device/dtype, so a tiny placeholder is enough.
        x = torch.zeros((1, k_np.shape[0], 1), device=self.device, dtype=self.dtype)
        with torch.inference_mode():
            cos, sin = self.rotary_emb(x, pos)
            _q, rotated = self.apply_rotary_pos_emb(q, k, cos, sin)
        return rotated.squeeze(0).permute(1, 0, 2).detach().float().cpu().numpy()
