# RC10 validation report

Date: 2026-10-04

## Host/native validation

- Configuration: CUDA disabled, Debug/O0 host qualification build.
- Clean CMake/Ninja build: PASS.
- Native CTest: **20/20 PASS**.
- New `qw3-kvmem-coherent-state` test: PASS.
- Existing RC9.2 host tests: retained and passing.

## Continual-control validation

- Python pytest: **18/18 PASS**.
- Affine composition equivalence: covered.
- Structural cache mismatch fail-closed: covered.
- Missing recurrent-layer rejection: covered.
- Post-qualification candidate mutation rejection: covered.
- Candidate path traversal rejection: covered.
- Future temporal fact filtering: covered.
- Replay sampling without duplicate rows: covered.
- FAST reconstruction composition + fixed seam policy: covered.

## Source/release integrity

- Release source audit: PASS.
- Source manifest: regenerated after all source/metadata changes and verified by
  the final host gate.

## Explicitly unqualified

No supported NVIDIA CUDA GPU/model checkpoint was available in the artifact
generation environment. The following remain unqualified and are not claimed
as complete: native Qwen Gated DeltaNet segment transition extraction,
full-stack seam/suffix replay, ReplaySSM/TreeWY integration, native QW3 LoRA
execution, and real-model HYPIC-style fidelity/performance benchmarks. Existing
RC9.2 exact selected replay remains the correctness oracle/fallback.
