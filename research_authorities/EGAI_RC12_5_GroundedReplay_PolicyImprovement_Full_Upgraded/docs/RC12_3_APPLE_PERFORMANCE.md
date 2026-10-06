# RC12.3 Apple Silicon performance plan

## Scope

RC12.3 improves the execution path around an immutable model. It does not claim that a faster backend is semantically equivalent until qualification proves that for the exact model/runtime/hardware closure.

## Performance order

### 1. Reduce weight bandwidth

Prefer a qualified 4-bit or 8-bit local model when quality is acceptable. The `optimize-mlx` command introspects the installed `mlx_lm.convert` CLI before constructing a quantization command, and writes a tree digest after conversion.

### 2. Keep the prompt smaller

Persistent memory is now bounded by a dedicated token budget. Retrieval may find six memories, but only memories fitting the configured token budget are injected. This directly attacks prefill time and prevents continual-memory growth from silently making every prompt slower.

### 3. Use native Apple execution

MLX/Metal is preferred for native Apple model execution; llama.cpp/Metal remains a first-class GGUF path. The Apple capability detector reports `mlx-metal` when native MLX is present.

### 4. Use backend-native cache and batching carefully

`apple-profile` estimates unified-memory pressure using the model weight footprint, a configurable KV/recurrent bytes-per-token estimate, workspace allowance, context size and parallel requests. The result is advisory until the exact model's memory behavior is measured.

### 5. Speculative decoding only when the installed runtime supports it

`backend-llama-fast` parses `llama-server --help`. If the user explicitly supplies `QW3_DRAFT_MODEL` but the installed server does not advertise `--model-draft`, startup fails rather than silently reverting to ordinary decoding.

### 6. HYPIC/KVMem last, after equivalence

The native Gated-DeltaNet/Metal and HYPIC work remains in the source tree, but production reuse of reconstructed recurrent state is still gated by:

`exact model weights + exact tokenizer + adapter set + runtime source closure + target Mac + recurrent/Conv state + attention relocation -> differential oracle -> qualification -> promotion`

## Metrics

RC12.3 measures the speed problem as separate quantities:

- TTFT: dominated by prompt prefill, context size and reusable execution state.
- decode tokens/sec: dominated by model bandwidth, kernels, quantization and speculative acceptance.
- total latency: useful but insufficient by itself.
- effective context size: persistent-memory injection must remain bounded.

A speedup is not accepted as a correctness result. Performance evidence is emitted separately from promotion authorization.
