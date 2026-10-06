# Native RC9.2 -> RC10 integration map

The bundled RC9.2 native runtime is retained under `native/kvmem-qw3-rc9.2` instead of being rewritten wholesale.

Relevant existing code:

- `src/gated_delta_net.cu` — real GDN recurrence and recurrent checkpoints.
- `src/kernels_cuda.cu` — recurrent batch integration.
- `src/kvmem_store.cpp` and archive/tier files — existing KVMem storage/runtime infrastructure.
- `docs/kvmem_deltanet_retrieval_*` — prior DeltaNet retrieval experiments.

RC10 integration should add a capture path that records, per recurrent layer/head, the affine tail transition and zero-state contribution for exactly `tokens[8:]`, plus the convolution/boundary material required to recompute `tokens[:8]` under a new predecessor.

Do not store one ambiguous block-level `(T,Z)` object. The native ABI must bind layer, head, orientation, seam width, tensor layout, dtype, and execution identity.

The standalone C++ reference in `experimental/rc10` validates affine composition independently of CUDA. Production work should next add GPU capture/compose kernels and paired exact-replay tests against the existing GDN kernel.
