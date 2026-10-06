# RC14.4 Release Notes — Measured Continual Learning

RC14.4 is the first RC14 release whose main additions are learning-science mechanisms rather than another authority plane.

The semantic belief-revision engine aggregates evidence by independent source, caps correlated repeated evidence from one producer, exposes contradictions, and emits a candidate belief without writing the authoritative belief store. The cross-task skill inducer requires verified support across multiple task families and then requires fresh held-out transfer on disjoint families; repeated success on the source task alone is insufficient.

Replay selection now ranks individual memories by estimated forgetting, importance, uncertainty, age, interference risk, and novelty while enforcing task-family diversity. The continual experiment harness computes fresh-task gain, forward/backward transfer, forgetting, interference, falsification survival, security regressions, resource growth, latency, and reproducibility. Experiment results are stored in a transactional hash-chained ledger and can be used as qualification evidence only when configured forgetting/security/falsification gates pass.

The authority boundary is unchanged: these components propose and measure; they do not qualify, promote, sign, or activate persistent changes.
