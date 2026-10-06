# Sequential Continual-Learning Benchmark

Evaluate at 0, 50, 100, 250, 500, 1000, 2500, 5000 verified experiences.

Hold out entire task families, not just instances. Report Generalization Rings R0-R6 separately. A benchmark item counts as evidence only when its evaluator is independent of the learner.

Primary condition for the frozen-core experiment:
- exact base-model hash unchanged;
- future-task performance rises;
- foundation retention stays within epsilon;
- no security regression;
- no unauthorized mutation;
- provenance closure 100%.

Ablation ladder:
A0 frozen model
A1 + episodic retrieval
A2 + skills
A3 + composition
A4 + grounded replay
A5 + active falsification
A6 + deterministic plasticity
A7 + qualified adapter candidates
A8 + imagined replay
A9 + learned plasticity proposer

Remove components that do not produce defensible held-out transfer or efficiency gains.
