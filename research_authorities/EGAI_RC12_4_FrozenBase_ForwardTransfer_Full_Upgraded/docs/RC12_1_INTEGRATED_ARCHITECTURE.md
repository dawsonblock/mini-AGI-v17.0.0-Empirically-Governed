# RC12.1 Integrated Architecture

RC12.1 keeps three validity domains explicit rather than flattening them into one implementation:

- `egai`: authoritative evidence, frozen-model continual learning, skills, benchmarks, independent build/evaluation/qualification/promotion.
- `kvcontinual.continual`: persistent experience/memory and continual runtime services.
- `kvcontinual.execution`: RC11.7 active coherent execution-memory runtime.
- `kvcontinual.rc1025`: namespaced RC10.25 target-Mac seam/tail/qualification reference so newer target-qualification mechanisms can be exercised without silently regressing RC11.7 invariants.

New governance glue adds FreshTaskAuthority, exact RuntimeClosure binding, R0-R6 transfer helpers, digest-only signer service, and direct frozen MLX-LM inference.

KVMem/HYPIC execution artifacts remain derived acceleration state, not truth-bearing evidence. Learning proposes changes; independent authorities qualify and promote them.

## Experimental research namespace

The EGAI v2.2 Dream-RSI/active-learning/plasticity implementation is retained under `egai_v22` as a research namespace rather than overwriting the stricter EGAI v3 authority path. This makes grounded replay, Dream Engine, transfer-selective replay, CapacityProbe, hypothesis registry, structural-distillation and meta-learning dataset code available for controlled experiments while preventing those experimental components from silently acquiring promotion authority.
