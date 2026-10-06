# v2.2 delta from v2.1

- Hardened evidence path: direct SQLite evidence writes now require an unforgeable process-local EvidenceAdmission capability.
- Added EvidenceQuarantine and EvidenceAdmissionService.
- Persistent derived state now has monotonic versions plus history; added authorized rollback.
- Added versioned BeliefStore.
- Added ActiveExperimentPlanner for information-gain-driven falsification.
- Added TransferSelectiveReplay.
- Dream engine now supports batch decisions and a Dream-RSI-like quality/cost/parallelism objective.
- FreshTaskAuthority now commits to hidden task hashes before release.
- Added StructuralDistiller that can only emit candidates.
- Added meta-learning dataset readiness gate; learned policy fails closed until sufficient records exist.
- Transfer metrics now report mean, breadth, conservative minimum-ring transfer, and constrained score.
- Promotion decisions are audit-appended and may carry rollback targets.
- Extended tests for admission bypass, rollback, holdout commitments, active learning, selective replay, structural distillation, and meta-learning fail-closed behavior.
