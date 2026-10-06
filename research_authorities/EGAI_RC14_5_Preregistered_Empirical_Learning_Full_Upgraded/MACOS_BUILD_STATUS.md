# RC14 macOS validation note

The macOS/Metal status below is inherited from the RC13.3.1 donor build. RC14.0 itself was validated in a Linux container and **was not re-qualified on Apple Silicon hardware in this build session**. Re-run the macOS qualification scripts before treating RC14 as Mac-qualified.

# Historical Mac runtime status inherited by RC11.4

This file documents the retained RC10.5 Mac/native baseline. The active consolidated release status is `FULL_UPGRADED_BUILD_STATUS.md`.

# Apple Silicon macOS build status

Release: **RC10.5 macOS Gated-DeltaNet reference profile**

## Implemented through RC10.5

- Everything in the RC10.4 controlled continual-learning profile.
- Apple Silicon installer, doctor, bootstrap, verification, test, benchmark, learning-cycle, and GDN-reference commands under `macos/`.
- llama.cpp/Metal and MLX local inference backend integration.
- Persistent SQLite temporal memory and authoritative experience ledger.
- Verified-episode dataset export and isolated MLX LoRA/QLoRA candidate training.
- Digest-bound adapter bundles, qualification, promotion authority boundary, rollback, and deterministic routing metadata.
- Host/fp64 implementation of the actual QW3 Gated-DeltaNet recurrence used by `src/gated_delta_net.cu`.
- Exact fixed-input `(T,Z)` token and segment composition.
- Independent Python and C++ parity tests plus a user-facing `gdn-check` smoke oracle.
- CUDA-on-macOS remains explicitly rejected rather than silently building a nonfunctional GPU path.

## Validation performed in the artifact-generation environment

- Native host CMake/Ninja build with CUDA disabled: **PASS**.
- Native CTest suite: **21/21 PASS**.
- Continual/control-plane/macOS tests: **33/33 PASS**.
- GDN reference smoke oracle: **PASS**.
- Python syntax/compile validation: **PASS**.
- macOS shell scripts: `bash -n` **PASS**.
- Source audit: **PASS**.
- Source manifest verification: **PASS**.

## Qualification boundary

The artifact-generation environment is Linux and does not contain Apple Metal hardware or the macOS SDK. Actual Apple Silicon compilation, model loading, Metal throughput, memory pressure, and backend-version behavior still require execution on the target Mac.

RC10.5 proves the recurrence algebra against QW3's CUDA implementation for fixed token-local inputs. It does **not** claim a native Metal KVMem port or exact arbitrary-segment deep-network reuse. Native Metal work still requires GDN input capture, structured `(T_C,Z_C)` generation, attention-KV relocation, seam/suffix repair, and exact-replay parity qualification.
