# EGAI v2.2 — Full Upgraded Controlled Continual Intelligence Kernel

This is a research implementation of a **governed continual-learning system**, not a claim of AGI or proven recursive self-improvement.

The core invariant is:

**Cognition != Learning Proposal != Verification != Promotion Authority**

v2.2 tightens the design around the final architecture: evidence admission is now capability-gated; all persistent derived state is promotion-gated and versioned; grounded replay has strict prefix observability; a Dream-RSI-style policy simulator, active falsification planner, transfer-selective replay, holdout commitments, structural-distillation proposals, meta-learning readiness gates, and rollback authority are included.

## What is implemented

- Immutable/hash-chained evidence and audit ledgers backed by SQLite.
- Quarantine -> evidence admission service; the raw store cannot be written without an admission capability.
- Origin/outcome typing to prevent simulation/model predictions from silently becoming evidence.
- Versioned beliefs/hypotheses as derived state.
- Executable/versioned skill graph and skill composition.
- Grounded replay worlds with enforced prefix-only outcome access.
- Policy Dream Engine with quality/cost/parallelism objective support.
- Model-imagined replay kept explicitly untrusted.
- Active experiment ranking by information gain / (cost + risk).
- Transfer-selective replay rather than uniform rehearsal.
- Deterministic Plasticity Proposer and CapacityProbe; L6-L9 fail closed initially.
- Candidate -> Build -> Evaluation -> Qualification -> Promotion -> Runtime hash chain.
- Ed25519 signed qualification and promotion receipts.
- FreshTaskAuthority commitments for hidden future-task evaluation.
- R1-R6 transfer vector and hard promotion constraints.
- Improvement Ledger and meta-learning dataset readiness gate.
- Proposal-only structural distillation.
- Versioned persistent state with authorized rollback/audit.
- Content-addressed artifact store and runtime closure verification.

## Quick start

```bash
python -m unittest discover -s tests -v
python -m egai.cli
python -m egai.verify_build
```

The first scientific target remains: improve hidden future-task performance with an exactly frozen base model before enabling neural adaptation.
