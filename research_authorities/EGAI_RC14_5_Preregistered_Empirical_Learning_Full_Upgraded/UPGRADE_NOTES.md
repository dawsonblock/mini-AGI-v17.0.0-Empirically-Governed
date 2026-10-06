# RC14.5 Preregistered Empirical Learning Upgrade

RC14.5 keeps the RC14.4 governance and measured-learning substrate and hardens the scientific path for L6 isolated neural memory.

## Added

- Immutable preregistered continual-experiment plans.
- Fixed six-stage ablation ladder; cherry-picked ladders are rejected.
- Multiple preregistered replicate seeds.
- Exact environment/task-set binding for every replicate.
- Hash-chained experiment-protocol events with duplicate-slot prevention and tamper verification.
- Derived ablation certificates requiring complete matrices, bounded forgetting, minimum fresh-task gain, incremental gain over replay, falsification survival, reproducibility, and zero configured security/authority regressions.
- Isolated-neural-memory manifests with capacity and parameter budgets.
- Frozen-foundation proofs that require unchanged base/tokenizer/frozen-parameter roots and confine all observed changes to the declared trainable scope.
- Replay-verified L6 experiment evidence in the qualification engine. A caller-supplied `qualified=true` flag is insufficient.
- Default governance now requires preregistered continual-experiment evidence for L6 persistence.

## Deliberate boundary

This release validates the experiment and qualification machinery using deterministic regression fixtures. It does not claim that a real large model has passed the full protocol. The next scientifically meaningful step is to run the sealed protocol on an actual frozen foundation model and publish/reproduce the resulting evidence bundles.
