# RC10.21 native Qwen tail-injection contract

RC10.21 separates four pieces that earlier releases could accidentally conflate:

1. **Fresh seam execution** — real model computation for the leading seam under the newly assembled predecessor.
2. **Recurrent cached tail** — apply each per-layer/value-head affine `(T,Z)` summary to the fresh recurrent state.
3. **Convolution state** — keep K-1 predecessor samples for seam reconstruction, but K latest raw projected samples for native single-token decode cache restoration.
4. **Full-attention cached tail** — append only tail K/V; keys are stored pre-RoPE and receive the new positions through the deployed model's own Qwen3.5 text rotary implementation.

The reference flow is:

```text
fresh seam through live Qwen
        |
        v
live recurrent/conv/KV seam cache
        |
        +-- recurrent tail: S <- T_tail S + Z_tail
        +-- conv decode: restore final K projected samples
        +-- attention tail: model-native MRoPE(new positions) + append K/V
        |
        v
state-plane digest + TailInjectionReceipt
```

`inject_qwen35_tail_into_transformers_cache` is a structural current-Transformers bridge. It intentionally requires batch size one and fails closed when the cache layout, recurrent-head coverage, convolution shape or position-reapply contract does not match.

## Why K-1 and K are both required

A causal convolution of kernel size K requires K-1 predecessor samples to compute the first relocated seam token. That is the boundary reconstruction object.

Current Transformers linear-attention decode caches, however, retain K raw projected samples and use them in the fused single-token update path. A K-1 boundary payload cannot safely masquerade as the native decode cache. RC10.21 stores both representations explicitly and binds both into the artifact content digest.

## Artifact ABI v4

Execution artifacts now serialize as `kvcontinual-execution-artifact-v4`. v1-v3 files are disposable derived state and must be regenerated from authoritative source tokens.

## Qualification status

The Python/reference contract is tested. Actual Qwen3.5 + MPS/Metal end-to-end HYPIC is still fail-closed until run on Apple Silicon and qualified against exact selected replay.
