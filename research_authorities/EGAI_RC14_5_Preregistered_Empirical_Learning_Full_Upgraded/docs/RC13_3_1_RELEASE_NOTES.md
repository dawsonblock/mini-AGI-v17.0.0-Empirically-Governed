# EGAI RC13.3.1 — Transactional StateEpoch hardening

RC13.3.1 is a correctness and authority release built from the mini-AGI v13 convergence trunk. It deliberately does not claim new general intelligence capability. Its purpose is to make future continual-learning experiments trustworthy enough to interpret.

## Primary changes

- Canonical CLI now targets `minagi.cli`; the legacy research CLI remains explicitly available as `egai-research`.
- RC11.8 governed activation components are present in the active execution namespace: signed runtime activation, monotonic control state, process locking, and governed runtime manifests.
- Evidence and improvement ledgers use SQLite WAL transactions plus process locking rather than ambiguous multi-file append sequences.
- Evidence objects are content addressed; model inference and replay are non-authoritative by default, while verified derivations require authoritative parents and a verification digest.
- Promoted skill revisions are immutable CAS objects. A conflicting promotion for the same `skill_id/version` is rejected rather than overwriting history.
- Promoted beliefs retain immutable revision history while a transactional head identifies the active revision.
- `StateEpoch` binds model, tokenizer, runtime manifest, belief snapshot, skill snapshot, memory/retrieval policies, adapter set, and promotion decision into one immutable request-visible generation.
- StateEpoch activation is signed, predecessor-bound, nonce/transition protected, and monotonic.
- Research-chain hardening restored revoked-key enforcement, finite/non-negative runner metric validation, and frozen-model identity checks after hidden evaluation.
- Local llama.cpp model identity is recalculated from current model/runtime bytes so checkpoint substitution is visible to the frozen-model guard.

## New release-blocking tests

- 12-process concurrent evidence ingestion with no ambiguous failures.
- Same-version skill conflict rejection and immutable history retention.
- Belief revision history preservation after active-head movement.
- Signed monotonic StateEpoch activation and stale-transition replay rejection.
- Revoked evaluator key rejection.
- NaN/Inf/negative runner metric rejection.
- Model-file mutation detection and final-evaluation identity recheck.

## Deliberate limits

RC13.3.1 does not enable autonomous foundation-weight updates. It does not claim that the reference skill synthesizer constitutes general skill induction. Real-weight Qwen/HYPIC/Metal qualification remains separate from the control-plane work in this release. Exact execution remains the fail-closed baseline unless a matching signed target qualification is bound.
