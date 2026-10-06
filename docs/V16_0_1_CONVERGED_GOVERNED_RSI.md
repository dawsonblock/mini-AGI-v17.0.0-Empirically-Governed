# mini-AGI v16.0.1 — Converged Governed RSI

## Purpose

v16.0.1 is an integration release, not a claim of AGI or demonstrated autonomous recursive self-improvement. It composes four previously separate strengths behind one authority boundary:

1. **v15.4 execution trunk** — measured governed serving, StateEpoch binding, learned-skill/adapter serving, native LM-head LoRA.
2. **EGAI RC12.4 scientific verifier** — frozen-base hidden forward-transfer evaluation, transfer rings, paired statistics, retention/foundation/security gates.
3. **Alpha9 proposal-side plasticity** — least-permanent-first adaptation ladder and calibration.
4. **Dream-RSI meta-exploration** — replay-driven search-policy optimization with replicated qualification and live-canary statistics.

The invariant is:

`proposal != scientific qualification != promotion authorization != execution`

Dream-RSI and the plasticity controller cannot promote or activate artifacts. The forward-transfer evaluator cannot mutate the running state. v16 convergence qualification is evidence-only. The existing promotion/StateEpoch authority remains the sole route into servable state.

## New v16 integration components

### `minagi.v16.plasticity_execution`
Alpha9 no longer has to accept a caller-populated `CapabilityClosureAttemptV149` as if it were an experiment. `PlasticityExecutionHarnessV160` executes mechanism runners in strict permanence order, hands their opaque artifacts to a separate evaluator callback, builds measured attempts, stops at the first sufficient lower-permanence mechanism, and returns proposal/qualification evidence only.

### `minagi.v16.dream_stats`
Dream-RSI's one-pass aggregate qualification is supplemented with paired replicated evaluation across unique replay seeds and a bootstrap confidence interval on the candidate-minus-baseline score. Search-policy changes can also require a replicated live canary with both quality and cost gates.

### EGAI RC12.4 forward transfer
The RC12.4 hidden forward-transfer authority is present unchanged as the scientific transfer plane. The v16 integration tests exercise R4/R5 future-transfer cases, retention, foundation retention, security cases, a frozen model digest, FreshTaskAuthority lease binding, and a signed evaluator receipt.

### `minagi.v16.isolated_solver`
A narrow JSON subprocess boundary is provided for candidate solvers so expected hidden answers and the vault key do not need to enter the candidate process. This is a process boundary with rlimits, not a complete hostile-code sandbox; production secrecy still requires a dedicated OS identity and sandbox/container/VM boundary.

### RuntimeClosure2
v15.4 measured foundation/model bytes, the running QW3 binary, KVMem manifest bytes, and native adapter bytes. RuntimeClosure2 adds direct byte measurement for:

- tokenizer file/tree;
- retrieval-policy file/tree;
- skill-policy file/tree.

Python measures these before launch, passes concrete paths to QW3, and native QW3 independently repeats the measurements. A mismatch in any measured root prevents governed serving. The `/v1/runtime/state` contract exposes the measured roots and the RuntimeClosure2 digest.

## Converged release gate

`ConvergedEvidenceBundleV160` binds:

- candidate digest;
- originating request digest;
- plasticity report digest;
- forward-transfer receipt digest;
- RuntimeClosure2 digest;
- Dream-RSI qualification digest when the search policy changed;
- whether the foundation changed.

`IndependentConvergedQualifierV160` evaluates those independent evidence channels and signs a qualification receipt. It deliberately has no promotion method.

Default policy requires:

- plasticity closure evidence;
- forward-transfer evidence;
- RuntimeClosure2 evidence;
- Dream-RSI evidence for search-policy changes;
- no foundation update.

## Validation performed for v16.0.1

Fresh validation in the build environment:

- primary Python suite: **293/293 passed**;
- imported Dream-RSI suite: **16/16 passed**;
- RC12.4 authority suite: **101/101 passed**;
- RC12.4 oracle-reference suite: **25/25 passed**;
- focused native RuntimeClosure2 canonical parity target: **PASS**.

The supplied v15.4 parent reported 27/27 portable native tests passing before this integration. A fresh full rebuild of all QW3 native targets was started but did not complete inside the execution window; therefore v16.0.1 does **not** claim a fresh 27/27 native rerun. The modified RuntimeClosure2 target was compiled and executed successfully.

## Nonclaims / remaining work

This release does not prove:

- positive forward transfer over a real 1,000–5,000+ task campaign;
- 10k–100k episode stability;
- all-linear attention/MLP LoRA in native QW3 (native application remains LM-head/output only);
- CUDA/GPU parity for the new integration;
- full adversarial isolation of hidden-task candidate code;
- independent third-party reproduction;
- autonomous recursive self-improvement.

The next scientifically meaningful milestone is not another architecture layer. It is a preregistered, long-horizon campaign that shows repeatable R4/R5 forward transfer while preserving retention/security, followed by activation of the exact qualified artifact under RuntimeClosure2.
