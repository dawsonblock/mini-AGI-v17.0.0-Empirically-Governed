from __future__ import annotations

from typing import Any, Callable

import numpy as np

from kvcontinual.rc1025.cache.block import ExecutionArtifact
from kvcontinual.rc1025.hybrid.seam_plan import SeamFirstSegmentPlan
from kvcontinual.rc1025.recurrent.affine import AffineSummary
from kvcontinual.rc1025.types import TransitionOrientation


PositionReapply = Callable[[int, np.ndarray, np.ndarray, Any], np.ndarray]


def _torch_apply_summary(summary: AffineSummary, state, torch):
    T = torch.as_tensor(np.asarray(summary.T), device=state.device, dtype=state.dtype)
    Z = torch.as_tensor(np.asarray(summary.Z), device=state.device, dtype=state.dtype)
    if tuple(state.shape) != tuple(Z.shape):
        raise ValueError(f"recurrent state shape {tuple(state.shape)} does not match cached Z {tuple(Z.shape)}")
    if summary.orientation == TransitionOrientation.LEFT_MULTIPLY:
        return T @ state + Z
    return state @ T + Z


def inject_qwen35_tail_into_transformers_cache(
    cache: Any,
    artifact: ExecutionArtifact,
    step: SeamFirstSegmentPlan,
    *,
    model_position_reapply: PositionReapply,
) -> None:
    """Inject one RC10 cached tail into a live current-Transformers Qwen cache.

    Preconditions:
      * the fresh seam for ``step`` has already run through the model;
      * ``cache`` therefore contains current recurrent/conv/KV seam state;
      * batch size is one (the current RC10 capture/qualification contract).

    The function updates exactly three state planes:
      1. GDN recurrent states via cached affine tail (T,Z),
      2. GDN convolution decode states via the distinct K-sample decode payload,
      3. full-attention K/V by appending only the relocated cached tail.

    This is intentionally structural and fail-closed. It relies only on the
    public cache update methods/fields used by current Transformers Qwen3.5 and
    does not pretend to support arbitrary future cache layouts.
    """
    import torch

    artifact.validate()
    if artifact.source_segment_id != step.source_segment_id:
        raise ValueError("Qwen cache injection artifact/source mismatch")
    if artifact.content_digest != step.artifact_content_digest:
        raise ValueError("Qwen cache injection artifact digest mismatch")
    if artifact.identity.digest != step.execution_identity_digest:
        raise ValueError("Qwen cache injection execution identity mismatch")
    if artifact.fixed_seam_width != step.seam_width:
        raise ValueError("Qwen cache injection seam mismatch")
    if model_position_reapply is None:
        raise ValueError("Qwen cache injection requires model-native position reapply")
    if not hasattr(cache, "layers") or not hasattr(cache, "update_recurrent_state") or not hasattr(cache, "update_conv_state") or not hasattr(cache, "update"):
        raise RuntimeError("Transformers cache structural contract mismatch")

    # 1) GDN recurrent states. Current Qwen uses one state entry per layer and
    # shape [B,V,Dk,Dv]. Apply each cached value-head affine map to B=1 state.
    by_layer: dict[int, list[tuple[int, Any]]] = {}
    for (layer, head), item in artifact.recurrent.items():
        by_layer.setdefault(layer, []).append((head, item))
    for layer, items in sorted(by_layer.items()):
        if layer >= len(cache.layers):
            raise RuntimeError(f"cache has no layer {layer}")
        layer_cache = cache.layers[layer]
        recurrent_states = getattr(layer_cache, "recurrent_states", None)
        if not isinstance(recurrent_states, dict) or recurrent_states.get(0) is None:
            raise RuntimeError(f"layer {layer}: fresh seam did not initialize recurrent state")
        current = recurrent_states[0]
        if current.ndim != 4 or current.shape[0] != 1:
            raise RuntimeError(f"layer {layer}: expected recurrent state [1,V,Dk,Dv]")
        expected_heads = list(range(current.shape[1]))
        supplied_heads = sorted(head for head, _ in items)
        if supplied_heads != expected_heads:
            raise RuntimeError(f"layer {layer}: cached recurrent heads do not cover live Qwen state")
        updated = current.clone()
        for head, item in items:
            updated[0, head] = _torch_apply_summary(item.tail_summary, current[0, head], torch)
        cache.update_recurrent_state(updated, layer)

    # 2) Native convolution decode state. Transformers keeps K projected samples
    # for single-token decode; the K-1 seam boundary object is not sufficient.
    for layer, decode_state in sorted(artifact.conv_decode_states.items()):
        decode_state.validate()
        if layer >= len(cache.layers):
            raise RuntimeError(f"cache has no layer {layer}")
        layer_cache = cache.layers[layer]
        conv_states = getattr(layer_cache, "conv_states", None)
        if not isinstance(conv_states, dict) or conv_states.get(0) is None:
            raise RuntimeError(f"layer {layer}: fresh seam did not initialize convolution state")
        live = conv_states[0]
        if live.ndim != 3 or live.shape[0] != 1:
            raise RuntimeError(f"layer {layer}: expected convolution state [1,C,K]")
        raw = torch.as_tensor(np.asarray(decode_state.history), device=live.device, dtype=live.dtype).unsqueeze(0)
        if tuple(raw.shape) != tuple(live.shape):
            raise RuntimeError(f"layer {layer}: cached decode convolution shape does not match live cache")
        # update_conv_state appends then retains the last K values; passing a full
        # K-sample payload therefore replaces the effective native decode state.
        cache.update_conv_state(raw, layer, conv_kernel_size=decode_state.kernel_size)

    # 3) Full-attention tail only. Current Qwen cache update expects [B,H,T,D].
    for layer, attn in sorted(artifact.attention.items()):
        seam = step.seam_width
        pre = np.asarray(attn.pre_rope_keys)[seam:]
        vals = np.asarray(attn.values)[seam:]
        pos = np.arange(step.new_position_start + seam, step.new_position_end, dtype=np.int64)
        if pre.shape[0] != step.tail_token_count or vals.shape[0] != step.tail_token_count:
            raise ValueError(f"layer {layer}: attention tail length disagrees with seam plan")
        rotated = np.asarray(model_position_reapply(layer, pre, pos, attn.relocation))
        if rotated.shape != pre.shape:
            raise ValueError(f"layer {layer}: model-native MRoPE changed cached key shape")
        # infer device/dtype from any existing live key cache when possible;
        # otherwise use the model-native reapply output dtype on CPU and let the
        # cache implementation reject incompatible placement.
        target_device = None
        target_dtype = None
        if layer < len(cache.layers):
            live_keys = getattr(cache.layers[layer], "keys", None)
            if live_keys is not None and hasattr(live_keys, "device"):
                target_device, target_dtype = live_keys.device, live_keys.dtype
            else:
                live_keys = getattr(cache.layers[layer], "key_cache", None)
                if live_keys is not None and hasattr(live_keys, "device"):
                    target_device, target_dtype = live_keys.device, live_keys.dtype
        key_t = torch.as_tensor(rotated, device=target_device, dtype=target_dtype).permute(1,0,2).unsqueeze(0)
        val_t = torch.as_tensor(vals, device=key_t.device, dtype=key_t.dtype).permute(1,0,2).unsqueeze(0)
        cache.update(key_t, val_t, layer)
