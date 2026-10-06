from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import numpy as np

from kvcontinual.rc1025.recurrent.affine import AffineSummary
from kvcontinual.rc1025.types import TransitionOrientation


class KeyHeadMapping(str, Enum):
    """How value heads select key heads in a grouped GDN implementation.

    Qwen3.5 / Hugging Face repeats each key head contiguously with
    ``repeat_interleave(num_v_heads // num_k_heads)``. The legacy RC9.2 CUDA
    path uses ``value_head % num_k_heads``. These are different layouts and
    must never be silently conflated.
    """

    QWEN_REPEAT_INTERLEAVE = "qwen_repeat_interleave"
    LEGACY_MODULO = "legacy_modulo"


def key_head_for_value_head(vh: int, num_k_heads: int, num_v_heads: int, mapping: KeyHeadMapping) -> int:
    if num_k_heads <= 0 or num_v_heads <= 0:
        raise ValueError("head counts must be positive")
    if not 0 <= vh < num_v_heads:
        raise ValueError("value head out of range")
    if mapping == KeyHeadMapping.LEGACY_MODULO:
        return vh % num_k_heads
    if mapping == KeyHeadMapping.QWEN_REPEAT_INTERLEAVE:
        if num_v_heads % num_k_heads:
            raise ValueError("Qwen repeat-interleave mapping requires num_v_heads divisible by num_k_heads")
        group = num_v_heads // num_k_heads
        return vh // group
    raise ValueError(f"unsupported key-head mapping: {mapping}")


def _softplus_stable(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return np.maximum(x, 0.0) + np.log1p(np.exp(-np.abs(x)))


def prepare_gdn_gates(
    alpha_raw: np.ndarray,
    beta_raw: np.ndarray,
    dt_bias: np.ndarray,
    ssm_a: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert Qwen-style raw GDN controls into multiplicative decay and beta.

    ``ssm_a`` is the negative continuous-time coefficient (for current Qwen3.5,
    ``-exp(A_log)``). The upstream model passes the resulting negative log-decay
    into the delta-rule kernel; RC10 summaries use the multiplicative decay, so
    this function exponentiates it before returning.
    """
    a = np.asarray(alpha_raw, dtype=np.float64)
    b = np.asarray(beta_raw, dtype=np.float64)
    dt = np.asarray(dt_bias, dtype=np.float64).reshape(-1)
    ssm = np.asarray(ssm_a, dtype=np.float64).reshape(-1)
    if a.ndim != 2 or b.shape != a.shape:
        raise ValueError("alpha_raw/beta_raw must have shape [T,V]")
    if dt.shape != (a.shape[1],) or ssm.shape != (a.shape[1],):
        raise ValueError("dt_bias/ssm_a must have shape [V]")
    log_decay = _softplus_stable(a + dt[None, :]) * ssm[None, :]
    decay = np.exp(log_decay)
    sigmoid_beta = np.empty_like(b)
    positive = b >= 0.0
    sigmoid_beta[positive] = 1.0 / (1.0 + np.exp(-b[positive]))
    eb = np.exp(b[~positive])
    sigmoid_beta[~positive] = eb / (1.0 + eb)
    return decay, sigmoid_beta


def capture_head_tail(
    k: np.ndarray,
    v: np.ndarray,
    decay: np.ndarray,
    beta: np.ndarray,
    *,
    seam_width: int = 8,
) -> AffineSummary:
    """Capture one GDN head's fixed-input HYPIC tail summary.

    The returned affine map represents tokens ``[seam_width:]`` only:

        S_out = T_tail @ S_in + Z_tail

    for the RC10 column-state orientation. This is exact for the supplied
    k/v/decay/beta inputs; it does not claim those inputs remain unchanged after
    relocating a segment behind a different predecessor.
    """
    k = np.asarray(k, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    g = np.asarray(decay, dtype=np.float64).reshape(-1)
    b = np.asarray(beta, dtype=np.float64).reshape(-1)
    if k.ndim != 2 or v.ndim != 2 or k.shape[0] != v.shape[0]:
        raise ValueError("k/v must be rank-2 and have the same token count")
    if g.shape != (k.shape[0],) or b.shape != (k.shape[0],):
        raise ValueError("decay/beta must have shape [T]")
    if not 0 <= seam_width < k.shape[0]:
        raise ValueError("seam_width must leave a non-empty cached tail")

    dk = k.shape[1]
    dv = v.shape[1]
    T = np.eye(dk, dtype=np.float64)
    Z = np.zeros((dk, dv), dtype=np.float64)

    for t in range(seam_width, k.shape[0]):
        kt = k[t]
        vt = v[t]
        gt = float(g[t])
        bt = float(b[t])
        kT = kt @ T
        kZ = kt @ Z
        T = gt * (T - bt * np.outer(kt, kT))
        Z = gt * (Z - bt * np.outer(kt, kZ)) + bt * np.outer(kt, vt)

    return AffineSummary(T, Z, TransitionOrientation.LEFT_MULTIPLY)


@dataclass(frozen=True)
class CapturedGDNHeads:
    seam_width: int
    key_head_dim: int
    value_head_dim: int
    num_k_heads: int
    num_v_heads: int
    key_head_mapping: KeyHeadMapping
    summaries: tuple[AffineSummary, ...]
    key_head_for_value: tuple[int, ...]

    @property
    def head_dim(self) -> int:
        """Legacy alias retained for square-head callers."""
        if self.key_head_dim != self.value_head_dim:
            raise AttributeError("head_dim is ambiguous when key/value dimensions differ")
        return self.key_head_dim

    def summary_for_v_head(self, head: int) -> AffineSummary:
        return self.summaries[head]


def capture_segment_tail_heads(
    k: np.ndarray,
    v: np.ndarray,
    decay: np.ndarray,
    beta: np.ndarray,
    *,
    seam_width: int = 8,
    key_head_mapping: KeyHeadMapping = KeyHeadMapping.QWEN_REPEAT_INTERLEAVE,
) -> CapturedGDNHeads:
    """Capture all value-head affine tails with an explicit key-head layout.

    Shapes:
      k:     [T, K, Dk]
      v:     [T, V, Dv]
      decay: [T, V]
      beta:  [T, V]

    Current Hugging Face Qwen3.5 repeats key heads contiguously before entering
    the GDN kernel, so the default mapping is ``QWEN_REPEAT_INTERLEAVE``.
    ``LEGACY_MODULO`` exists only for compatibility with the bundled RC9.2
    native layout and must be selected explicitly.
    """
    k = np.asarray(k, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    decay = np.asarray(decay, dtype=np.float64)
    beta = np.asarray(beta, dtype=np.float64)
    if k.ndim != 3 or v.ndim != 3:
        raise ValueError("k/v must have shape [T,H,D]")
    if k.shape[0] != v.shape[0]:
        raise ValueError("k/v token count must match")
    Tn, K, Dk = k.shape
    V, Dv = v.shape[1], v.shape[2]
    if K <= 0 or V <= 0:
        raise ValueError("head counts must be positive")
    if decay.shape != (Tn, V) or beta.shape != (Tn, V):
        raise ValueError("decay/beta must have shape [T,V]")
    if not 0 <= seam_width < Tn:
        raise ValueError("seam_width must leave a non-empty cached tail")

    summaries: list[AffineSummary] = []
    mapping: list[int] = []
    for vh in range(V):
        kh = key_head_for_value_head(vh, K, V, key_head_mapping)
        mapping.append(kh)
        summaries.append(
            capture_head_tail(
                k[:, kh, :],
                v[:, vh, :],
                decay[:, vh],
                beta[:, vh],
                seam_width=seam_width,
            )
        )
    return CapturedGDNHeads(
        seam_width, Dk, Dv, K, V, key_head_mapping, tuple(summaries), tuple(mapping)
    )


def direct_head_recurrence(
    state: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    decay: np.ndarray,
    beta: np.ndarray,
) -> np.ndarray:
    """Direct one-head recurrence oracle for fixed supplied GDN inputs."""
    S = np.asarray(state, dtype=np.float64).copy()
    k = np.asarray(k, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    decay = np.asarray(decay, dtype=np.float64).reshape(-1)
    beta = np.asarray(beta, dtype=np.float64).reshape(-1)
    if k.ndim != 2 or v.ndim != 2 or k.shape[0] != v.shape[0]:
        raise ValueError("k/v must be rank-2 with matching token count")
    if S.shape != (k.shape[1], v.shape[1]):
        raise ValueError("state must have shape [Dk,Dv]")
    for t in range(k.shape[0]):
        predicted = k[t] @ S
        delta = (v[t] - float(decay[t]) * predicted) * float(beta[t])
        S = float(decay[t]) * S + np.outer(k[t], delta)
    return S
