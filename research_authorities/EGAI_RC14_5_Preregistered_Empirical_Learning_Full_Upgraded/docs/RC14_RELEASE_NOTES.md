# RC14.0.1 Release Notes

RC14.0 is a convergence release, not a feature-count release. It preserves RC13.3.1 as the proven substrate and adds a new `minagi.rc14` layer rather than replacing working authority paths with weaker v14 scaffolding.

## Integrated from RC13.3.1

- SQLite/WAL transactional evidence and immutable revisions.
- Governed runtime activation and exact-mode fallback.
- Canonical `egai -> minagi.cli` packaging.
- Signed monotonic state transition patterns.
- Independent research-chain qualification and promotion separation.

## Integrated from mini-AGI v14

- Permanence × evidence governance coordinates.
- Proposal-only Dream search.
- Fresh one-shot hidden tasks.
- Falsification classes and preregistration.
- Model-time replay scheduling.

The original v14 `CandidateStateStore` was **not** copied as authority because it read state before entering its write transaction and only syntactically checked authorization digests. RC14 replaces it with a process-locked, `BEGIN IMMEDIATE`, signed-transition lifecycle.

## Integrated from RC13.0

- Expanded StateEpoch closure.
- PREPARED → AUTHORIZED → LOCALLY_COMMITTED → EXTERNALLY_WITNESSED → ATTESTED → SERVABLE lifecycle.
- Request-level serving epoch leases.
- Monotonic rollback-by-new-epoch semantics.

## Default safety boundary

Automatic/persistent activation is capped at `L6_ISOLATED_NEURAL_MEMORY`. `L7_SHARED_ADAPTER`, `L8_NEW_MODULE`, `L9_FOUNDATION_CONSOLIDATION`, and `L10_ARCHITECTURE_CHANGE` are represented so the research plane can propose them, but default policy rejects activation.
