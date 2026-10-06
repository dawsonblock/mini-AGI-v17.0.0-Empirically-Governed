# RC14 Validation Boundary

RC14 adds direct tests for:

- default permanence/evidence policy and proposal-only L7+ behavior;
- signed candidate authorization and receipt substitution rejection;
- process-level candidate transition races with exactly one winner;
- rich StateEpoch lifecycle and monotonic rollback preparation;
- request epoch pinning;
- one-shot hidden-task consumption and commitment reveal;
- preregistered falsification with exact case coverage;
- proposal-only Dream search;
- adaptive replay and explicit forgetting/transfer/interference metrics.

The inherited RC13.3.1 test suite remains the regression baseline.

Not established by this release: large-scale continual-learning improvement, independent reproduction of model-level gains, safe shared-adapter learning, foundation consolidation, autonomous architecture mutation, or production deployment qualification.
