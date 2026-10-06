# Coherent Hybrid Continual Memory RC10 release notes

RC10 merges the qualified RC9.2 QW3/KVMem native runtime with a hardened
coherent-memory and continual-learning foundation.

## Added

- Native host/reference affine segment summaries `(T_C, Z_C)` with ordered
  composition tests.
- Fail-closed execution-cache identity covering model, adapters, tokenizer,
  layer layout, position scheme and recurrence implementation.
- Strict recurrent-layer-set validation: missing layers cannot silently vanish
  during composition.
- Adaptive seam/suffix reconstruction policy primitives while retaining exact
  selected replay as the correctness oracle.
- Recurrent-summary metadata hooks in `KvMemBlock`.
- Hardened `continual/` control plane with persistent temporal memory,
  replay, candidate adapters, digest-bound qualification, promotion and
  rollback.
- Separate memory and admin mutation APIs.

## Correctness/security repairs relative to the RC10 prototype

- Post-qualification adapter mutation is detected before promotion.
- Candidate IDs cannot traverse outside the registry namespace.
- Structural cache changes are invalid instead of heuristically approximate.
- Persistent memory no longer defaults to `:memory:` in the API.
- Future-dated facts are not considered current.
- Supersession is atomic.
- Replay samples do not duplicate the same stored row in one batch.
- FAST reconstruction returns the composed state and performs fixed seam repair.

## Certification boundary

The native host suite and Python continual suite are qualified by
`scripts/release/host_gate.sh`.

Target-GPU implementation/qualification remains required for real Qwen
Gated-DeltaNet `(T,Z)` extraction, seam/suffix replay, ReplaySSM/TreeWY, native
LoRA execution, and model-level coherence benchmarks. RC9.2 exact selected
replay remains the correctness fallback until those gates pass.

See `docs/RC10_COHERENT_CONTINUAL_MERGE.md` and
`docs/RC10_IMPLEMENTATION_STATUS.md`.

## RC10.5 macOS recurrence-reference extension

The Apple Silicon source profile adds an independent host/fp64 implementation of the exact QW3 Gated-DeltaNet state recurrence used in `src/gated_delta_net.cu`. It verifies per-token affine `(T,Z)` construction, block composition, zero-start `Z_C`, and direct token-replay parity. This is a correctness reference for future Metal capture/composition work; it does not claim native Metal execution or arbitrary deep-network segment equivalence.
