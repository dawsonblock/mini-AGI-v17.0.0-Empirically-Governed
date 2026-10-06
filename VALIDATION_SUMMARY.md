# Validation Summary — v15.4.0

Local validation completed for this exact source tree before release packaging.

- Python suite: **277 passed, 0 failed** with third-party pytest plugin autoload disabled.
- Focused RuntimeClosure1 Python tests: **5 passed, 0 failed**.
- Host-native QW3 executable: **compiled successfully** with `QW3_ENABLE_CUDA=OFF`.
- Portable native C++ suite: **27 passed, 0 failed**.
- New native closure test proves the C++ canonical served-artifact root and closure digest match Python's canonical JSON/SHA-256 rules.
- Model-directory tree hashing has deterministic Python/C++ parity coverage.
- QW3 now verifies actual model bytes, its own executable bytes and attached KVMem manifest bytes before governed serving.
- An inconsistent component set or aggregate `artifact_root` prevents server startup rather than becoming a claimed governed identity.
- Existing native LoRA bundle byte verification and request-time epoch/manifest/artifact/adapter checks remain active.

Environment limitation: `nvcc` and CUDA hardware were unavailable. Real model weights and real-task A0/A1 improvement were not executed. Tokenizer, retrieval-policy and skill-policy roots are included in the recomputed artifact root but are not yet independently materialized/byte-measured by native QW3.
