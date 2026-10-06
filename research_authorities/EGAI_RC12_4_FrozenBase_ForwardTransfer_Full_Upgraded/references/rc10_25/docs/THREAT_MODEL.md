# Threat model and failure containment

RC10.16-macOS assumes retrieved memories, approximate reconstruction, freshly trained adapters, and model outputs can all be wrong.

Primary failure classes are stale execution artifacts after a model/adapter/fast-weight change; poisoned or false semantic memory; hidden-state drift after arbitrary segment transplantation; seam-contract errors that double-process or omit tokens; transition orientation/layout mistakes; catastrophic forgetting in candidate adapters; benchmark overfitting; malformed artifact manifests; and a serving process gaining unintended mutation authority.

Controls include immutable source segments; temporal/provenanced semantic memory; exact model/execution identity; fixed seam-width semantics; explicit transition orientation; explicit convolution-boundary state; RoPE-aware attention relocation; capture-manifest completeness; exact selected replay; sampled shadow replay; candidate/production separation; digest-bound adapter manifests; regression and cache-quality gates; staged cache namespaces; atomic promotion/rollback; and no requirement for the serving process to hold registry mutation authority.

This repository is not an OS or GPU security sandbox. Native model code, training jobs, downloaded weights, and kernel toolchains still need deployment-appropriate isolation and supply-chain controls.
