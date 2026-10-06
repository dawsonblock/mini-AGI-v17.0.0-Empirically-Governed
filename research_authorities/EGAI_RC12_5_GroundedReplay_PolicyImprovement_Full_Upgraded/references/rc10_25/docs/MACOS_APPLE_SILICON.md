# RC10.18 macOS / Apple Silicon

RC10.18 is the correctness-first Apple Silicon build of Coherent Hybrid Continual Memory. CUDA-only execution is never relabeled as Metal, and the Mac runtime does not advertise HYPIC reuse merely because the affine recurrence algebra is available.

## Qwen3.5 live-capture delta

RC10.18 adds a concrete structural capture adapter for the current Hugging Face Qwen3.5/3.6-style hybrid text decoder. It records the actual hidden state entering each target layer, reconstructs local GDN projection/convolution intermediates without modifying model output, captures full-attention K/V before position rotation, and materializes execution-artifact ABI v2.

The adapter is qualification-oriented rather than optimized: local projections are recomputed inside forward pre-hooks so tensor semantics stay inspectable. A future native/Metal shim can replace that capture implementation without changing the durable source-memory or execution-artifact contracts.

For GDN, RC10.18 uses Qwen's grouped/repeat-interleave key-head mapping. Legacy modulo-mapped artifacts are not accepted as RC10.18 production cache state. The layout digest also binds the actual linear key/value head counts, key/value dimensions, convolution kernel width, and layer pattern.

For attention, Qwen artifacts store pre-RoPE keys and use `MODEL_REAPPLY_PRE_ROPE`. RC10 does not pretend its generic pairwise 1-D RoPE helper is Qwen3.5's production relocation rule; the deployed model's own position embedding must be applied at the target positions.

For causal convolution, the execution artifact stores the **outgoing** `kernel_size-1` raw convolution-input history from the source segment. That is the boundary object needed when the following selected segment is attached. The independently captured segment's old incoming history is not treated as portable truth.

## Supported now

- Python 3.11+ RC10 control plane on macOS.
- Transformers + PyTorch MPS exact selected-token replay, with CPU fallback.
- MLX/NumPy affine `(T,Z)` reference execution.
- Fixed-input Gated DeltaNet/HYPIC tail capture in NumPy and Metal reference kernels.
- Qwen hybrid model layout discovery and fixed seam-8 capture-manifest generation.
- Real Qwen3.5/3.6 structural pre-hook capture through `Qwen35TransformersLiveCapture`.
- Qwen grouped GDN head mapping and rectangular `Dk/Dv` recurrent-state support.
- Causal-convolution outgoing-boundary materialization and seam reference replay.
- Pre-RoPE full-attention K/V capture with explicit model-reapply relocation metadata.
- Execution-artifact v2 persistence, content digests, cache namespaces, and qualification receipts.
- Exact replay oracle and fail-closed reconstruction routing.
- Metal reference kernels for affine execution, GDN preparation/recurrence/tail capture, and causal-convolution seam replay.

## Real-model capture

Generate an execution identity tied to the deployed model/runtime:

```bash
python scripts/generate_execution_identity.py /path/to/model \
  --base-weights-digest sha256:<weights> \
  --tokenizer-digest sha256:<tokenizer> \
  --output execution_identity.json
```

Inspect the hybrid layout:

```bash
python scripts/inspect_hybrid_model.py /path/to/model --seam 8
```

Capture one authoritative source segment:

```bash
python scripts/capture_qwen35_segment.py /path/to/model \
  --text "source segment" \
  --source-id segment-001 \
  --identity-json execution_identity.json \
  --output segment-001.npz
```

Validate the resulting derived artifact:

```bash
python scripts/validate_execution_artifact.py segment-001.npz
```

Capture alone does **not** qualify arbitrary reuse. The artifact remains disposable derived state until accelerated execution is compared with exact selected replay and an evidence-bound qualification receipt is issued.

## Still not claimed complete

RC10.18 is not yet a production Qwen3.5 HYPIC runtime on macOS. The remaining work is execution rather than capture.

A production integration must:

1. assemble the selected source-token topology and fixed seam-8 plan;
2. execute each leading seam through the deployed model under the new predecessor's live recurrent, convolution, and attention state;
3. apply the cached GDN tail `(T,Z)` only after the fresh seam, without double-processing seam tokens;
4. reapply the deployed model's own position embedding to cached pre-RoPE attention keys at target positions;
5. append/reuse full-attention tail state with the exact selected-token history;
6. compare accelerated execution against exact selected replay over adversarial deletion, reordering, duplication, relocation, and multi-fragment workloads;
7. qualify the path on actual Apple Silicon/Metal hardware and bind the evidence to the artifact/runtime identity;
8. only then advertise `hypic_seam8=True` from the production Mac backend.

The generic Transformers/MPS backend therefore remains exact-only.

## Why artifact ABI v2 is intentionally incompatible

RC10.17 v1 artifacts were produced under different recurrent head-mapping and convolution-boundary semantics. RC10.18 rejects them rather than migrating stale neural state. Regenerate v2 artifacts from authoritative source tokens.

This follows the core invariant:

> No cached neural artifact is more authoritative than the source tokens from which it can be regenerated.

## Qualification receipts

A production accelerated backend can set `requires_artifact_qualification=True`. RC10 then refuses reuse unless the receipt binds at least:

- execution/model identity;
- artifact content digest;
- capture-manifest identity;
- same-hidden-input GDN algebra validation;
- convolution-boundary completeness;
- attention-relocation completeness;
- exact-oracle qualification evidence;
- hardware/runtime fingerprint.

This prevents a reference artifact or stale cache from becoming production accelerated state merely because its Python type is valid.

## Build on Apple Silicon

```bash
./scripts/setup_macos.sh
source .venv/bin/activate
python -m pytest -q
./scripts/build_macos_native.sh
```

The native Mac script builds the RC9.2 host-only preset with CUDA/FlashInfer/server execution disabled, then compiles the reference Metal library and runs the available affine, GDN/HYPIC, and causal-convolution smoke programs on Apple hardware.

## Exact replay baseline

```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
python scripts/run_macos_exact_example.py /path/to/model
```

Exact selected replay remains the permanent correctness oracle.
