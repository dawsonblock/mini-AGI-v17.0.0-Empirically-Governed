# RC10.5 Mac validation report

Date: 2026-10-04

Host validation in the artifact environment:

- CMake/Ninja, CUDA disabled: PASS
- CTest: 21/21 PASS
- Continual/macOS pytest: 33/33 PASS
- GDN reference composition smoke test: PASS
- Source audit: PASS
- Source manifest: PASS

The GDN reference directly mirrors `src/gated_delta_net.cu`:

`S' = gS + k [beta(v - g S^T k)]^T = g(I-beta k k^T)S + beta k v^T`.

A deterministic 64-token, d=16 reference run produced max-absolute composition error approximately `2.08e-17`, consistent with fp64 roundoff.

No claim is made that Apple Metal kernels have been executed or qualified in this environment.
