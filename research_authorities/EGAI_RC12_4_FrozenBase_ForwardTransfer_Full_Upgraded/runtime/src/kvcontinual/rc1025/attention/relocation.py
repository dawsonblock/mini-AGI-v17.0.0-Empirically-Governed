from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import numpy as np


class AttentionRelocationStrategy(str, Enum):
    """How cached full-attention keys acquire positions after relocation."""
    # Generic mathematical helper for ordinary pairwise 1-D RoPE only.
    PAIRWISE_ROPE_DELTA = "pairwise_rope_delta"
    # Preferred Qwen3.5 path: cache keys before RoPE and invoke the deployed
    # model's own position-embedding implementation for the new positions.
    MODEL_REAPPLY_PRE_ROPE = "model_reapply_pre_rope"


@dataclass(frozen=True)
class FullAttentionRelocationMetadata:
    layer: int
    token_count: int
    source_position_start: int
    keys_are_rope_rotated: bool
    rope_digest: str
    stores_pre_rope_keys: bool = False
    strategy: str = AttentionRelocationStrategy.PAIRWISE_ROPE_DELTA.value

    def validate(self) -> None:
        if self.layer < 0 or self.token_count < 0 or self.source_position_start < 0:
            raise ValueError("invalid attention relocation metadata")
        if not self.rope_digest:
            raise ValueError("rope_digest is required")
        strategy = AttentionRelocationStrategy(self.strategy)
        if strategy == AttentionRelocationStrategy.MODEL_REAPPLY_PRE_ROPE:
            if not self.stores_pre_rope_keys or self.keys_are_rope_rotated:
                raise ValueError("model-reapply strategy requires unrotated pre-RoPE keys")


def rope_digest(inv_freq: np.ndarray) -> str:
    a = np.ascontiguousarray(inv_freq, dtype=np.float64)
    return "sha256:" + hashlib.sha256(a.tobytes()).hexdigest()


def rope_apply(x: np.ndarray, positions: np.ndarray, inv_freq: np.ndarray) -> np.ndarray:
    """Apply ordinary pairwise 1-D RoPE to token-major keys/queries.

    This is a generic reference helper. It is NOT the Qwen3.5 interleaved MRoPE
    implementation; Qwen3.5 artifacts use MODEL_REAPPLY_PRE_ROPE instead.
    """
    x = np.asarray(x)
    pos = np.asarray(positions, dtype=np.float64)
    inv = np.asarray(inv_freq, dtype=np.float64)
    if x.ndim < 2 or x.shape[0] != pos.shape[0]:
        raise ValueError("x must be token-major and match positions")
    d = x.shape[-1]
    if d % 2 or inv.shape != (d // 2,):
        raise ValueError("invalid RoPE dimensions")
    angles = pos[:, None] * inv[None, :]
    expand = (slice(None),) + (None,) * (x.ndim - 2) + (slice(None),)
    c = np.cos(angles)[expand]
    s = np.sin(angles)[expand]
    even = x[..., 0::2]
    odd = x[..., 1::2]
    out = np.empty_like(x, dtype=np.result_type(x.dtype, np.float64))
    out[..., 0::2] = even * c - odd * s
    out[..., 1::2] = even * s + odd * c
    return out.astype(x.dtype, copy=False)


def relocate_rope_keys(rotated_keys: np.ndarray, old_positions: np.ndarray, new_positions: np.ndarray, inv_freq: np.ndarray) -> np.ndarray:
    """Relocate already-rotated keys for ordinary pairwise 1-D RoPE only."""
    old = np.asarray(old_positions)
    new = np.asarray(new_positions)
    if old.shape != new.shape:
        raise ValueError("old/new positions must have the same shape")
    return rope_apply(rotated_keys, new - old, inv_freq)
