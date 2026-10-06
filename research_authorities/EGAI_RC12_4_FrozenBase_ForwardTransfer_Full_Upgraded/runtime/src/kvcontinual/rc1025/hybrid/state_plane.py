from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

import numpy as np

from kvcontinual.rc1025.recurrent.conv_boundary import ConvBoundaryState, ConvDecodeState


def _hash_array(h: "hashlib._Hash", value: Any) -> None:
    a = np.ascontiguousarray(value)
    h.update(str(a.dtype).encode("utf-8"))
    h.update(json.dumps(list(a.shape), separators=(",", ":")).encode("utf-8"))
    h.update(a.tobytes())


@dataclass
class AttentionCacheState:
    """Concrete attention cache for one layer after relocation.

    Keys are already position-encoded for their current assembled positions.
    Values are position independent. The state is deliberately token-major so a
    backend can translate it to its native KV layout without changing the RC10
    integrity contract.
    """

    keys: np.ndarray
    values: np.ndarray
    positions: np.ndarray

    def validate(self) -> None:
        k = np.asarray(self.keys)
        v = np.asarray(self.values)
        p = np.asarray(self.positions)
        if k.ndim < 2 or v.ndim < 2:
            raise ValueError("attention cache keys/values must be token-major arrays")
        if k.shape[0] != v.shape[0]:
            raise ValueError("attention cache key/value token counts differ")
        if p.ndim != 1 or p.shape[0] != k.shape[0]:
            raise ValueError("attention cache positions must match key/value token count")
        if p.size and np.any(np.diff(p.astype(np.int64)) != 1):
            raise ValueError("attention cache positions must be contiguous")

    def append(self, keys: np.ndarray, values: np.ndarray, positions: np.ndarray) -> None:
        self.validate()
        keys = np.asarray(keys)
        values = np.asarray(values)
        positions = np.asarray(positions, dtype=np.int64)
        if keys.ndim < 2 or values.ndim < 2 or keys.shape[0] != values.shape[0]:
            raise ValueError("appended attention keys/values must be token-major")
        if positions.ndim != 1 or positions.shape[0] != keys.shape[0]:
            raise ValueError("appended attention positions mismatch")
        if self.positions.size and positions.size and int(positions[0]) != int(self.positions[-1]) + 1:
            raise ValueError("attention tail does not continue the current assembled position sequence")
        self.keys = np.concatenate([np.asarray(self.keys), keys], axis=0)
        self.values = np.concatenate([np.asarray(self.values), values], axis=0)
        self.positions = np.concatenate([np.asarray(self.positions, dtype=np.int64), positions], axis=0)
        self.validate()


@dataclass
class HybridExecutionState:
    """Backend-neutral state planes after fresh seam execution.

    This state contains only execution data for the *current* ExecutionIdentity.
    It is not durable knowledge. RC10.21 uses it to make cached-tail injection a
    deterministic, auditable state transition before a native backend converts
    the arrays into Metal/MLX/Transformers-native layouts.
    """

    execution_identity_digest: str
    token_count: int = 0
    recurrent: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)
    conv: dict[int, ConvBoundaryState] = field(default_factory=dict)
    conv_decode: dict[int, ConvDecodeState] = field(default_factory=dict)
    attention: dict[int, AttentionCacheState] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.execution_identity_digest.startswith("sha256:"):
            raise ValueError("HybridExecutionState requires an ExecutionIdentity digest")
        if self.token_count < 0:
            raise ValueError("token_count cannot be negative")
        for (layer, head), state in self.recurrent.items():
            if layer < 0 or head < 0:
                raise ValueError("recurrent layer/head indices must be non-negative")
            if np.asarray(state).ndim < 2:
                raise ValueError("recurrent states must be matrix-like")
        for layer, state in self.conv.items():
            if layer < 0:
                raise ValueError("convolution layer indices must be non-negative")
            state.validate()
        for layer, state in self.conv_decode.items():
            if layer < 0:
                raise ValueError("convolution decode layer indices must be non-negative")
            state.validate()
            if layer in self.conv and self.conv[layer].kernel_size != state.kernel_size:
                raise ValueError("seam/decode convolution kernel sizes disagree")
        for layer, state in self.attention.items():
            if layer < 0:
                raise ValueError("attention layer indices must be non-negative")
            state.validate()
            if state.positions.size and int(state.positions[-1]) >= self.token_count:
                raise ValueError("attention cache position extends beyond assembled token_count")

    @property
    def digest(self) -> str:
        self.validate()
        h = hashlib.sha256()
        h.update(self.execution_identity_digest.encode("utf-8"))
        h.update(str(self.token_count).encode("utf-8"))
        for key in sorted(self.recurrent):
            h.update(f"r:{key[0]}:{key[1]}".encode("utf-8"))
            _hash_array(h, self.recurrent[key])
        for layer in sorted(self.conv):
            c = self.conv[layer]
            h.update(f"c:{layer}:{c.kernel_size}".encode("utf-8"))
            _hash_array(h, c.history)
        for layer in sorted(self.conv_decode):
            c = self.conv_decode[layer]
            h.update(f"cd:{layer}:{c.kernel_size}".encode("utf-8"))
            _hash_array(h, c.history)
        for layer in sorted(self.attention):
            a = self.attention[layer]
            h.update(f"a:{layer}".encode("utf-8"))
            _hash_array(h, a.keys)
            _hash_array(h, a.values)
            _hash_array(h, a.positions)
        return "sha256:" + h.hexdigest()
