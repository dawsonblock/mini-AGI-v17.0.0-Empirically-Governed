# RC14 Build Plan and Status

## Completed in RC14.0

1. Fork RC13.3.1 as the production substrate.
2. Preserve canonical `egai -> minagi.cli`; retain `egai-research` separately.
3. Add one authoritative RC14 candidate lifecycle with process serialization and signed privileged transitions.
4. Add permanence × evidence governance policy with L7-L10 proposal-only by default.
5. Add richer immutable StateEpoch closure.
6. Add signed PREPARED/AUTHORIZED/COMMITTED/WITNESSED/ATTESTED/SERVABLE transitions.
7. Add request epoch pinning and lease records.
8. Add monotonic rollback-by-new-epoch preparation.
9. Add process-safe one-shot fresh-task authority.
10. Add preregistered falsification plans and exact result coverage checks.
11. Add proposal-only Dream scoring with transfer/interference/compute/security/falsification terms.
12. Add adaptive model-time replay.
13. Add explicit forgetting, forward-transfer, backward-transfer, and interference metrics.
14. Add RC14-specific regression/adversarial tests and preserve the RC13 suite.

## Completed in RC14.1

- Added external FreshTask service process support and encrypted-at-rest hidden-task storage.
- Added fail-closed `ExecutionContextGuard` and request epoch pinning for reconstruction.
- Added measured component resolvers and stronger candidate/promotion closure.
- Preserved separate RC13 and RC14 StateEpoch registries.

## Completed in RC14.2

- Added role-scoped authenticated FreshTask evaluator/admin capabilities.
- Added immutable falsification-run persistence and replay-safe revalidation.
- Added derived qualification evidence and signed evidence-attestation support.
- Bound qualification records to derived evidence and reject mismatched claimed flags.
- Added request-source epoch/request binding for governed request-derived learning.
- Added candidate-derived promotion closure for StateEpoch preparation.
- Added cross-plane deep verification and fresh portable native requalification.

## Completed in RC14.3

- Added typed independently signed external-witness artifacts bound to the committed transition head.
- Added typed runtime-attestation artifacts bound to the measured serving/runtime closure.
- Made the canonical RC14 runtime reject opaque witness/attestation digests.
- Made SERVABLE derive witness/attestation identity from signed transition history.
- Added whole-request `request_context()` epoch pinning.
- Hardened FreshTask secret-file permissions and symlink handling.
- Freshly requalified the portable native suite.

## Next release gates

### RC14.4
- Add bi-temporal semantic-belief revisions and contradiction proposals.
- Add real skill induction across unrelated transfer tasks.
- Add replay-memory prioritization from measured rather than predicted forgetting.

### RC14.5+
- Run controlled sequential-learning experiments and ablations.
- Only after reproducible L0-L6 gains should shared-adapter (`L7`) qualification be considered.
- Keep foundation consolidation (`L9`) and architecture change (`L10`) disabled until independent reproduction and explicit operator authorization are demonstrated.

## Completed in RC14.4
- Proposal-only semantic belief revision with contradiction handling and source-correlation caps.
- Cross-task skill induction with disjoint fresh held-out transfer requirements.
- Diversity-aware adaptive replay prioritization.
- Measured continual-learning and ablation harness with immutable experiment ledger.
- Fresh portable native qualification retained.

## Completed in RC14.5
- Preregistered complete continual-learning ablation protocol.
- Multi-seed immutable experiment matrix with hash-chain verification.
- Incremental-gain-over-replay, forgetting, falsification, security, and reproducibility qualification gates.
- Isolated-neural-memory manifest and frozen-foundation/trainable-scope proof.
- Replay-verified L6 experiment evidence bound into qualification.

## Next release gates
- Execute the protocol against a real frozen large model rather than synthetic fixtures.
- Add independent evaluator/reproducer evidence packages for actual model runs.
- Do not enable L7 shared-adapter persistence unless L6 produces replicated fresh-OOD gains without unacceptable forgetting.
