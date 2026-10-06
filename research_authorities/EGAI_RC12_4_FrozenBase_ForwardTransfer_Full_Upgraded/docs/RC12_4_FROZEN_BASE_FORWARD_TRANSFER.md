# RC12.4 Frozen-Base Forward Transfer Qualification

RC12.4 is the first release whose primary purpose is to test whether the governed continual-learning stack improves performance on **unseen future task families while the base model remains byte-identical**.

## Scientific target

The release is built around the falsifiable condition:

\[
P_{future}(E_n) > P_{future}(E_0) \quad \text{while} \quad \theta_n=\theta_0.
\]

The target is not training-set improvement. The primary emphasis is R4/R5 transfer: new task families with related structure and new environments/interfaces.

## New authority path

1. The benchmark authority preregisters the hypothesis, model digest, experience-stream digest, hidden-suite commitment, checkpoints, alpha and stop conditions.
2. Hidden evaluation tasks are serialized and sealed with AES-256-GCM.
3. FreshTaskAuthority commits the sealed-suite digest and issues a one-time candidate-bound lease.
4. The independent evaluator decrypts the hidden suite only inside the verifier boundary.
5. Baseline and candidate are evaluated on identical hidden cases.
6. R0-R6 paired effects are measured with bootstrap intervals and an exact one-sided sign test.
7. Holm-Bonferroni correction controls family-wise error across tested transfer rings.
8. Retention, foundation-retention and security gates are evaluated independently of the transfer metric.
9. The base-model digest is checked before and after evaluation.
10. Raw paired results are stored as a content-addressed artifact and the evaluator emits a signed aggregate receipt.

The encrypted task-vault API is an integrity primitive, not a substitute for operating-system isolation. Production hidden-task evaluation should run under a separate verifier process/account whose key and plaintext suite are inaccessible to the learner.

## Ablation ladder

- B0: frozen model
- B1: episodic/evidence retrieval
- B2: procedural skills
- B3: skill composition
- B4: transfer-selective replay
- B5: active experimentation

A stage should advance only if it adds held-out forward transfer or a preregistered efficiency gain while preserving all hard gates.

## Hard gates

- exact frozen-model digest remains constant;
- positive aggregate forward transfer;
- sufficient transfer breadth;
- R4 and R5 are present and have positive confidence intervals;
- R4/R5 survive Holm-corrected sign tests;
- old-task retention remains above threshold;
- foundation capability remains above threshold and inside the allowed regression budget;
- security score does not regress;
- hidden-suite lease is valid and candidate-bound;
- evaluation evidence is independently signed.

## Deliberately still disabled

RC12.4 does not automatically promote LoRA/adapters, learn the plasticity controller, update shared base weights, or modify architecture. Those mechanisms remain downstream experiments. A failure to obtain frozen-base forward transfer must be diagnosed at the evidence/retrieval/skill/composition/replay layers rather than hidden by additional plasticity.

## Apple execution relationship

RC12.3.1 target-Mac qualification is retained intact. Execution acceleration and continual-learning qualification remain separate validity domains: a HYPIC/Metal speedup must be proven equivalent on the target Mac, while RC12.4 capability improvement must be proven on hidden future tasks.
