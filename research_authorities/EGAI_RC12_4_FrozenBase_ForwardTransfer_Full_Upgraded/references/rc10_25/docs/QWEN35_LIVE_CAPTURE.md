# Qwen3.5 / Qwen3.6 live capture contract — RC10.18

RC10.18 adds a concrete, fail-closed capture adapter for the current Hugging Face Qwen3.5 text stack. The adapter is intended for correctness qualification and artifact materialization, not as the final low-overhead production hook.

## Upstream computation matched by this adapter

The current Qwen3.5 Gated DeltaNet path performs, in order:

1. `in_proj_qkv(hidden_states)`;
2. depthwise causal convolution + activation;
3. split into query, key and value;
4. reshape key heads and value heads separately;
5. `beta = sigmoid(in_proj_b(hidden_states))`;
6. negative log-decay `g = -exp(A_log) * softplus(in_proj_a(hidden_states) + dt_bias)`;
7. repeat key/query heads with `repeat_interleave(num_v_heads // num_k_heads)`;
8. L2-normalize Q/K inside the GDN kernel with epsilon `1e-6`;
9. execute the recurrent/chunked delta rule.

RC10 stores the multiplicative decay `exp(g)` because the affine transition is expressed directly in state-update form.

For Qwen3.5-4B, the published config currently uses:

- 16 GDN key heads;
- 32 GDN value heads;
- 128-dimensional key heads;
- 128-dimensional value heads;
- causal convolution kernel size 4;
- a 3-linear-attention : 1-full-attention layer pattern;
- interleaved multimodal RoPE parameters.

The resulting value-head → key-head map is grouped/repeat-interleaved: value heads `0,1` use key head `0`, heads `2,3` use key head `1`, and so on. This is **not** the historical `vh % num_k_heads` mapping in the bundled RC9.2 CUDA source.

## What the structural adapter captures

`kvcontinual.hybrid.qwen35_transformers.Qwen35TransformersLiveCapture` installs forward-pre-hooks on the actual GDN and full-attention modules selected by the capture manifest. The hook receives the real hidden input entering each layer and recomputes only the local projections needed to expose otherwise-hidden cache inputs.

For each GDN layer it emits:

- normalized key vectors `[T, K, Dk]`;
- values `[T, V, Dv]`;
- multiplicative decay `[T, V]`;
- beta `[T, V]`;
- raw token-major convolution input `[T, C]`;
- the independent-capture incoming convolution history;
- boundary hidden anchors;
- explicit `qwen_repeat_interleave` head-mapping metadata.

For each full-attention layer it emits:

- keys **before** positional rotation;
- values;
- source token positions;
- boundary hidden anchors.

## Corrected convolution-boundary semantics

RC10.17 persisted the incoming convolution history of an independently captured segment. That is not the useful boundary object for transplanting the *next* segment.

RC10.18 materializes the **outgoing raw-convolution input history** after the source segment: the final `kernel_size - 1` pre-convolution samples. This is stored once per GDN layer rather than duplicated in every value-head transition object.

When a new segment is attached, the predecessor's outgoing history is the boundary state used to recompute the fresh seam.

## Corrected attention-position semantics

Qwen3.5 uses interleaved multimodal RoPE. RC10.18 therefore does not claim that the generic pairwise one-dimensional `relocate_rope_keys()` reference is the production Qwen relocation rule.

Qwen3.5 execution artifacts use:

`MODEL_REAPPLY_PRE_ROPE`

The artifact stores the unrotated key and the backend must apply the **currently deployed model's own position-embedding implementation** at the new assembled positions. The model's position configuration digest is part of `ExecutionIdentity` and the artifact relocation metadata.

## Artifact ABI break

The corrected head mapping and convolution semantics change artifact meaning. The persisted artifact format is therefore:

`kvcontinual-execution-artifact-v2`

RC10.17 `v1` artifacts are rejected and must be regenerated from authoritative source tokens. No hidden-state artifact is migrated as if it were knowledge.

## Operator workflow

Inspect the live model contract:

```bash
python scripts/inspect_hybrid_model.py /path/to/Qwen3.5-4B --seam 8
```

Generate an exact execution identity after supplying cryptographic digests for your exact weights/tokenizer/adapter set:

```bash
python scripts/generate_execution_identity.py /path/to/Qwen3.5-4B \
  --base-weights-digest sha256:... \
  --tokenizer-digest sha256:... \
  --adapter-manifest-digest sha256:none \
  --output execution-identity.json
```

Capture one source segment:

```bash
python scripts/capture_qwen35_segment.py /path/to/Qwen3.5-4B \
  --text "source material longer than the fixed seam" \
  --identity-json execution-identity.json \
  --source-id source-001 \
  --output source-001.npz
```

Capturing and materializing an artifact does **not** qualify it for HYPIC reuse. The exact-replay qualification harness must still issue an evidence-bound qualification receipt on the target Apple Silicon execution environment.

## Remaining production boundary

RC10.18 closes live tensor extraction and cache-object semantics. It still does not claim a production full-model HYPIC executor on macOS. Remaining work is:

- execute the fresh seam through the actual Qwen stack while injecting the predecessor convolution state;
- apply cached recurrent tails at the correct layer boundaries;
- reapply the deployed Qwen MRoPE implementation to cached pre-RoPE keys at new positions;
- splice those K/V tensors into the live attention cache;
- propagate corrected seam activations through later layers;
- qualify arbitrary deletion/reordering against exact selected-token replay on Apple Silicon;
- only then set `hypic_seam8=True` in a production Mac backend.

Until that is complete, full-model execution remains exact selected replay on the generic Transformers/MPS backend.
