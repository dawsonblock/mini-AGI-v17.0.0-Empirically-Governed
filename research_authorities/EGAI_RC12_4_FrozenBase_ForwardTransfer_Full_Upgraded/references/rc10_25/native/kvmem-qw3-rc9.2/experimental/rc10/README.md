# RC10 native affine reference

This directory adds a dependency-free C++17 correctness reference beside the bundled RC9.2 native runtime. It mirrors the state orientation used by `src/gated_delta_net.cu` and verifies that per-token GDN affine maps compose exactly when the underlying token-local operators are held fixed.

It is not a production HYPIC CUDA implementation. Its purpose is to pin the ABI and algebra before optimizing capture/composition kernels.

Build:

```bash
g++ -std=c++17 affine_reference_test.cpp -o /tmp/rc10_affine_test
/tmp/rc10_affine_test
```
