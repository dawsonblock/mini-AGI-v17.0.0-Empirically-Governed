# Alpha9 Adaptive Plasticity

Alpha9 adds an empirical, least-permanent capability-closure layer on top of Alpha8. It does **not** create a new promotion or mutation authority.

## Core rule

A mechanism may be selected only after all lower-permanence mechanisms in the preregistered ladder have been empirically tested and found insufficient. Forecasts are retained for calibration but cannot establish sufficiency.

Default ladder:

1. current context
2. retrieval
3. episodic memory
4. semantic memory
5. skill
6. skill composition
7. JIT non-parametric policy adaptation
8. temporary activation adaptation
9. modular adapter
10. foundation update

Modular adapters and foundation updates remain disabled by default.

## Capability-closure evidence

Each attempt binds predicted and realized success, interference, compute, retention, causal ablation, security regressions, latency, and evidence digests. The router stops at the first mechanism that passes the active policy. Continuing to test more permanent mechanisms after a lower-permanence mechanism passed is rejected.

## Forecast calibration

Predicted success, interference, and compute cost are compared with realized outcomes. Calibration receipts are immutable evidence; they do not grant mutation authority.

## JIT policy adaptation

The Alpha9 JIT policy is non-parametric and ephemeral. It estimates action value from trajectory/evidence-backed samples for an exact context digest and returns a decision receipt. It does not modify foundation weights or active learned-state heads. Production requires an external sample validator so JIT samples must cross an independent evidence/trajectory authority boundary.

## Production boundary

Production mode requires an exact `adaptive_plasticity_qualification_digest` in addition to Alpha8 release/dependency/native/FreshTask/scientific qualification evidence. The bundled adaptive mechanics fixture is synthetic and is **not** a real-world adaptive-plasticity qualification.
