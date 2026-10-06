# EGAI / KVContinual RC12.5 — Grounded Replay Policy Improvement

Version: **12.5.0**

RC12.5 retains RC12.4 frozen-base forward-transfer qualification and RC12.3.1 target-Mac execution qualification, then adds the first authoritative DREAM-RSI-style **grounded historical policy-improvement path**. The release deliberately optimizes exploration/retrieval/skill-selection policy over recorded evidence before enabling model-based imagination.

## What changed

- prefix-only grounded replay policy views;
- legal-action enforcement and replay budgets;
- every replayed outcome must bind to an evidence digest;
- encrypted AES-256-GCM held-out replay suites;
- paired baseline-vs-candidate replay evaluation;
- bootstrap confidence intervals and exact paired sign testing;
- replay-policy gates for mean gain, win/loss rate, cost growth, evidence closure, and holdout size;
- signed replay-policy preregistration/qualification receipts;
- raw replay results stored as content-addressed artifacts;
- offline qualification is **never deployable by itself**;
- a second evidence-backed live-canary authority is mandatory;
- live-canary success only makes a policy promotion-eligible; independent promotion still remains separate;
- model-predicted/counterfactual replay remains disabled in the authoritative path.

## Authority flow

```text
Historical evidence
   -> sealed held-out replay suite
   -> signed replay-policy plan
   -> baseline/candidate prefix-only replay
   -> signed offline qualification receipt
   -> real evidence-backed live canary
   -> signed canary receipt
   -> independent promotion authority
```

This is intentionally not a self-authorizing RSI loop. Replay can propose and qualify a better policy; it cannot deploy itself.

## Retained systems

RC12.5 keeps the frozen-base forward-transfer experiment, FreshTaskAuthority, hidden task vault, R0-R6 transfer statistics, target-Mac MLX/Metal qualification, KVMem/HYPIC research runtime, transactional governance data plane, signer separation, rollback, source closure, adapter gates, and model-digest invariance.

## Still disabled

- model-based imagined worlds in the authoritative evaluator;
- automatic adapter promotion;
- learned plasticity authority;
- shared-weight online learning;
- architecture self-modification.

The next scientific step after RC12.5 is to demonstrate that a replay-qualified policy improves **new online trajectories**, not merely historical replay score. Only then should calibrated model-based imagination be considered.
