# Qwen hybrid integration contract

RC10.18-macOS keeps Qwen tensor semantics behind a versioned structural adapter rather than hard-coding them into the control plane. The native backend must implement the `ReconstructionBackend` protocol and bind every artifact to an exact `ExecutionIdentity`.

For a hybrid full-attention + Gated DeltaNet model, the implementation responsibilities are:

1. Materialize an `ExecutionArtifact` from authoritative `SourceSegment` tokens.
2. Capture per recurrent layer/head tail summaries for exactly `tokens[8:]` under the native state orientation.
3. Preserve enough causal-convolution boundary material and original boundary anchors to replay `tokens[:8]` under a new predecessor.
4. Relocate/rebuild the full-attention cache for the same logical selected-token order.
5. Execute arbitrary-PIC reconstruction in seam-first order: fresh boundary, then cached recurrent/attention tail.
6. Provide `EXACT_SELECTED_REPLAY` from the source tokens as the reference path.
7. Provide `EXACT_PREFIX_REPLAY` from exact checkpoints for genuine canonical/shared-prefix continuation.
8. Optionally provide a LinearKV-style single-state initializer as a measured competing approximation.

Tail-Replay and SuffixReplay should be integrated only behind a prefix-compatible topology gate until arbitrary-transplant semantics are independently demonstrated.

Any change to adapter weights, adapter ordering/scales/composition, base weights, runtime learning state, or other computation that feeds cached layers is `REPLAY_REQUIRED` by default.

## RC10.18 Qwen capture + Apple reference primitives

`kvcontinual.recurrent.hypic_capture` provides the fixed-input algebraic oracle used to qualify a native backend. `native/kvmem-qw3-rc9.2/experimental/rc10_metal/rc10_gdn_reference.metal` mirrors the GDN recurrence and dense seam-tail `(T,Z)` capture. RC10.18 adds `Qwen35TransformersLiveCapture`, which populates the stable capture buffer from actual layer inputs for current Hugging Face Qwen3.5/3.6-style modules, then materializes v2 execution artifacts with grouped key-head mapping, outgoing causal-convolution history, and pre-RoPE attention K/V. This closes the capture layer but not the execution layer: production HYPIC still requires seam-first injection through the live model, model-native MRoPE reapplication, exact-oracle qualification and Apple-hardware evidence.
