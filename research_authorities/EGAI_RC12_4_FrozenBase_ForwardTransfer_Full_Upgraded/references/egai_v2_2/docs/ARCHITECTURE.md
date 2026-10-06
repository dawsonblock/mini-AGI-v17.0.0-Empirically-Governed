# EGAI v2.2 Architecture

## Governing hypothesis
A continually learning agent can improve forward-transfer efficiency by separating fast evidence acquisition from slow plasticity, extracting reusable procedures and abstractions, replaying grounded histories counterfactually, selecting the least-permanent adequate change, and independently qualifying all persistent changes against fresh hidden tasks.

## Authority planes
1. Cognitive Plane: solve and act; ephemeral working state.
2. Learning Plane: hypotheses, skills, replay/dreaming, plasticity proposals; no persistent commit authority.
3. Verification Plane: hidden transfer, retention, OOD, calibration, security, ablation, adversarial regression.
4. Promotion Plane: sole persistent derived-state commit and rollback authority.

Evidence admission is a separate gate: raw observations enter quarantine, then a trusted admission policy may append grounded evidence. This prevents a model-generated or simulated result from certifying itself.

## Memory/validity domains
- Working state: ephemeral activations/latent state.
- Evidence: immutable observations/actions/outcomes/provenance.
- Beliefs/hypotheses: mutable derived interpretations.
- Skills: executable governed procedures.
- Replay worlds: historical observed branches only.
- Imagination: untrusted model predictions.
- Execution memory: KV/recurrent/HYPIC state, separate from semantic truth.
- Parametric memory: adapters/modules/base weights; highest blast radius.

## Learning cycle
Experience -> Quarantine -> Evidence -> Prediction Error -> Hypothesis -> Procedure/Abstraction -> Counterexample Search -> Grounded Dreaming -> Real Falsification -> Transfer -> Plasticity Proposal -> Build -> Independent Qualification -> Promotion.

## Escalation
L0 working state; L1 evidence; L2 beliefs; L3 skills; L4 routing/policy; L5 composition; L6 adapter; L7 module expansion; L8 shared consolidation; L9 architecture modification.

Use the least-permanent mechanism that solves the problem. Evidence requirements and qualification rigor increase with permanence/blast radius.

## Dreaming
Grounded Dreaming may re-evaluate branch ordering, skill/routing choices, compute allocation, stopping, and other policies over recorded outcomes. Prefix observability is enforced structurally. Unexplored branches may be predicted only by an explicitly untrusted imagination service; these predictions may nominate real experiments but may never satisfy evidence requirements.

## Meta-learning
The initial Plasticity Proposer is deterministic. A learned proposer remains disabled until the Improvement Ledger contains a configured minimum number of independently qualified records. It remains advisory and cannot modify promotion rules, holdout authority, verifier keys, or audit history.
