# RC14.1 Release Notes

RC14.1 is the first post-hotfix convergence release after RC14.0.1. The release focuses on trust-boundary enforcement rather than adding new intelligence abstractions.

## Added

- `FreshTaskAuthorityServer` / `FreshTaskAuthorityClient` Unix-domain-socket service boundary.
- `egai-fresh-task-authority` daemon entry point.
- `ExecutionContextGuard` using a context-local pinned request epoch.
- Cross-candidate qualification/decision/authorization rejection in StateEpoch closure.
- Candidate AUTHORIZED-state gating before system-owned StateEpoch preparation.
- Regression tests for service isolation, one-shot hidden-task consumption, context fail-closed behavior, and promotion-chain candidate consistency.

## Retained

- RC13.3.1 transactional evidence/skill/belief and runtime substrate.
- RC14.0.1 artifact-bound candidate lifecycle, AuthorityState, signed StateEpoch lifecycle, encrypted-at-rest fresh tasks, reconstructive verification, signed retirement, and measured system-owned StateEpoch fields.
- Default L7-L10 proposal-only boundary.

## Qualification boundary

The Python/control-plane suites are validated in the current Linux environment. Native C++ sources are unchanged from RC14.0.1; a fresh native rebuild was attempted but exceeded the command execution ceiling, so RC14.1 does not present a new native CTest result as current evidence.
