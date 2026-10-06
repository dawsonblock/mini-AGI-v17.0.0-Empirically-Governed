# EGAI RC12.5 Grounded Replay Policy Improvement — Full Upgraded Build Status

RC12.5.0 retains RC12.4 frozen-base forward-transfer qualification, RC12.3.1 target-Mac execution qualification, and RC12.2.1 authority hardening, then adds an authoritative grounded historical replay policy-improvement path.

Implemented:
- canonical 12.5.0 release identity;
- prefix-only grounded replay policy evaluator;
- evidence-digest closure for every selected replay outcome;
- legal-action and budget enforcement;
- AES-256-GCM encrypted held-out replay histories;
- paired baseline/candidate replay statistics;
- signed replay policy plans and qualification receipts;
- content-addressed raw replay result artifacts;
- mandatory real live-canary authority;
- fail-closed rule: neither offline replay nor live canary can deploy a policy;
- model-predicted/counterfactual replay excluded from the authoritative path.

Validation completed in the generation environment:
- merged Python runtime suite: **194/194 passed**;
- new grounded replay/live-canary suite: **7/7 passed**;
- Python compileall: passed;
- shell syntax validation: passed;
- offline wheel build: passed;
- final source-closure and ZIP CRC checks are performed after tree freeze.

Portable native C++ was not rebuilt in this generation run because the rebuild exceeded the available run-time budget; the native source is inherited unchanged from RC12.4.
