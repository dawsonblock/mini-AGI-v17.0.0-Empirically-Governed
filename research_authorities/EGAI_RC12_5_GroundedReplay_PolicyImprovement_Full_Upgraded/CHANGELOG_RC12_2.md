# RC12.2 Changelog

RC12.2 hardens the RC12.1 convergence around persistence, falsifiability, replay integrity, interference control and escalation discipline.

## Added

- WAL-backed, versioned GovernanceDataPlane with optimistic version checks and hash-linked revisions.
- Durable FreshTaskStore so hidden-suite generations cannot be silently reused after authority restart.
- ExperienceGraph for explicit evidence/belief/hypothesis/skill/task relations without treating the graph itself as truth.
- TransferSelectiveReplayPlanner using compatibility, threat probability, transfer value and cost.
- InterferenceEstimator with weighted and worst-case regression gates.
- ReplayWorldCompiler that reconstructs historical prefixes from visibility timestamps.
- Statistical qualification helper with preregistered effect thresholds and conservative alpha spending.
- CausalCreditAssigner using paired counterfactual baselines.
- Hash-chained AuditJournal for cross-plane observability.
- LocalSubprocessSandbox reference boundary with CPU/memory/file-descriptor/time limits and fail-closed network capability requests.
- AdapterEscalationGate enforcing frozen-base verification and exhaustion of cheaper mechanisms before L6 adaptation.
- MetaPlasticityDataset and readiness threshold; learned plasticity remains disabled.
- AtomicRuntimePointer and full-runtime state closure for reversible activation/rollback.
- SignerService hardening: Unix socket mode 0600 and replay-resistant request IDs.

## Correctness rule retained

Learning and plasticity components may propose persistent changes. Only independent qualification and promotion authorities may authorize them.
