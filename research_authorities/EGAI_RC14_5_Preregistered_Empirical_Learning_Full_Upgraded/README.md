# EGAI Converged RC14.5

RC14.5 is a governed complementary continual-learning research runtime built on the RC13.3.1 transactional substrate and the RC14.4 measured-learning layer. It retains signed candidate/StateEpoch authority, authenticated hidden-task evaluation, request epoch pinning, witnessed runtime closure, immutable belief/skill histories, rollback/recovery controls, and explicit continual-learning metrics.

The RC14.5 change closes the next scientific-evidence gap: an L6 isolated-neural-memory claim can no longer qualify from a favorable metric bundle alone. The experiment must be preregistered before results exist and must execute the fixed ablation ladder:

```text
frozen -> retrieval -> semantic_memory -> skills -> replay -> isolated_neural_memory
```

The plan binds the candidate, frozen model, tokenizer, environment, task set, hidden-task commitment, replicate seeds, forgetting limits, transfer threshold, falsification threshold, and reproducibility threshold. Results outside the sealed variant/seed matrix are rejected.

Isolated neural memory additionally requires a frozen-foundation proof: the base-model identity, tokenizer identity, and frozen-parameter root must remain unchanged; observed parameter changes must stay inside the declared isolated trainable scope; and capacity/parameter budgets are checked.

The authority rule remains:

```text
Research / learning proposal
        !=
Experiment evidence
        !=
Qualification
        !=
Promotion authorization
        !=
StateEpoch activation
```

## Canonical commands

```bash
egai version
egai inspect-root <runtime-root>
egai rc14-inspect <runtime-root>
egai-fresh-task-authority --help
```

## Validation

The exact RC14.5 release tree passed **236 active Python**, **101 retained authority-reference**, and **25 retained oracle-reference** tests: **362 current-release tests passed, 0 failed**. The RC14-specific convergence/learning subset passed **42/42**. Native source is unchanged from RC14.4; its 25/25 result is recorded as inherited because the fresh RC14.5 compile exceeded the execution ceiling before completing.

## What is not claimed

RC14.5 validates the preregistration, ablation, isolation, replay-verification, and authority plumbing with deterministic tests. It does **not** demonstrate a large-model continual-learning gain, independent scientific reproduction, macOS/Metal qualification, CUDA qualification, AGI, or autonomous recursive self-improvement. L7-L10 remain proposal-only under the default policy.
