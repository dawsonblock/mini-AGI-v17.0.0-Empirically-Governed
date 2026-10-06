# RC9.2 validation report

Date: 2026-10-04

## Host validation

The RC9.2 working tree was configured with CUDA disabled and tests enabled. The
native host suite passed **19/19** after the deterministic repairs, including
scheduler lease fencing, physical-runtime lease fencing, strict workspace
binding, and the internal bound-session lookup regression.

Final sealing additionally runs:

- `scripts/release/source_audit.py`;
- a clean `scripts/release/host_gate.sh` build/test/CLI contract run;
- `scripts/release/verify_manifest.py`;
- Python KVMem evaluation unit tests;
- NEMO adapter TypeScript type-check where the packaged toolchain permits it.

The machine used to generate this artifact has no `nvcc`, so CUDA compilation and
runtime tests cannot be truthfully reported as passed here.

## CUDA-dependent changes requiring target qualification

RC9.2 changes CUDA behavior in two retrieval-index paths:

1. ExactMass uses constant-with-block-count dynamic shared memory and a three-pass
   exact softmax-mass calculation. `qw3-kvmem-exactmass-largeblocks` exercises
   13,001 blocks to prevent regression to the former shared-memory ceiling.
2. Boundary mean-key capture uses the already-existing incremental CUDA merge
   primitive from decode as well as resumed prefill; `qw3-kvmem-kmean-merge`
   covers split/replay/sub-block arithmetic.

These tests are packaged but **NOT RUN** in this host-only environment. Run
`scripts/release/gpu_gate.sh` on the intended NVIDIA architecture and pinned
model before calling RC9.2 GPU-qualified.

## Research boundary

KVMI-012 is not disguised as a release bug fix. Arbitrary sparse attention block
selection does not imply an exact transformation of DeltaNet recurrent state.
One-shot selected-replay rebuilds both representations from the same selected
source sequence. Persistent above-budget selected-replay combinations remain
fail-closed until a scientifically validated state-decomposition/reconstruction
method exists.
