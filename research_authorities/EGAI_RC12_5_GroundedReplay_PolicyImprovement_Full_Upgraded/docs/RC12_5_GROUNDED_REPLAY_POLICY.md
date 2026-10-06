# RC12.5 Grounded Replay Policy Improvement

## Goal

Use completed, evidence-backed trajectories as low-cost replay simulators for testing alternative exploration policies without granting replay the authority to create facts or deploy itself.

## Core invariant

A candidate policy receives only the observable prefix at decision time, legal actions, previously selected grounded outcomes, and remaining budget. It never receives future outcomes or unselected action outcomes.

## Grounded versus imagined

The authoritative RC12.5 evaluator accepts only `GroundedOutcome` records carrying an evidence digest. Model-predicted/counterfactual outcomes remain outside this validity domain.

## Holdout protocol

Held-out replay episodes are encrypted at rest with AES-256-GCM. A signed plan binds the exact sealed suite digest, baseline policy digest, candidate policy digest, objective, and gates before evaluation.

## Qualification

Baseline and candidate policies run on identical replay episodes. Qualification checks paired mean gain, bootstrap CI, one-sided sign test, win/loss rates, cost growth, evidence closure, and minimum holdout size.

Passing offline replay sets `qualified_offline=true` but `deployable=false`. A separate live canary is mandatory.

## Live canary

The live-canary authority consumes evidence-backed real outcomes. Passing it sets `promotion_eligible=true` but still `deployable=false`. Final activation remains the responsibility of independent PromotionAuthority.

## Why this order

Grounded replay is much easier to audit than model imagination. It lets the system improve retrieval, exploration, skill-selection, stopping, and compute-allocation policies while keeping historical evidence and promotion authority independent.
