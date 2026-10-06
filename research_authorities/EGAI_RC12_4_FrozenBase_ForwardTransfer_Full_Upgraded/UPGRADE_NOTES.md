# RC10.5 model-specific Gated-DeltaNet reference

- Added a CPU/fp64 reference mirroring `src/gated_delta_net.cu` state-update algebra.
- Added exact per-token `T = g(I - beta k k^T)` and `Z = beta k v^T` construction.
- Added exact block `(T_C,Z_C)` composition and zero-start-state verification.
- Added direct token-by-token replay and state-error oracles.
- Added stable raw alpha/beta preprocessing helpers matching the CUDA gate semantics.
- Added native and Python parity tests plus `macos/qw3-mac gdn-check`.
- Fixed `macos/run_all_tests.sh` so continual tests load repository configs independent of caller working directory.
- Native Metal GDN/TZ capture is still not claimed complete.

# RC10.4 Mac controlled continual learning

- Added persistent SQLite experience/training state alongside JSONL diagnostics.
- Added explicit episode verification before training eligibility.
- Added verified-example MLX dataset export and non-promoting offline learning worker.
- Added full MLX adapter-directory digest binding and mutation detection.
- Added backend capability reporting and deterministic adapter routing metadata.
- Added llama.cpp preload/hot-switch and request-local LoRA routing support.
- Added Mac bootstrap/verify/test/benchmark/learning-cycle commands.
- Preserved the authority boundary: training and qualification do not imply production promotion.

# KVMem/QW3 Coherent Hybrid Continual Memory RC10

RC10 merges RC9.2's real native runtime with a strict coherent-memory foundation
and hardened continual-learning control plane. It fixes the RC10 prototype's
cache-compatibility, missing-layer, artifact-substitution, path-traversal,
persistence, temporal-validity, and replay-sampling defects. Model-specific GDN
transition capture/seam replay and native LoRA execution remain explicit GPU
integration work rather than being claimed complete.

See `docs/RC10_COHERENT_CONTINUAL_MERGE.md`.

# KVMem/QW3 Hardening RC9.1

RC9.1 is the correctness-hardening revision built on RC9. It does not expand the
CUDA certification boundary beyond one native executor slot.

## RC9.1 changes

- exact scheduler lease-ID fencing;
- exact physical runtime lease-ID fencing (`executor-slot-runtime-v2`);
- separate monotonic physical lease tokens with scheduler-lease linkage for persistent sessions;
- stale physical reset/release rejection;
- bound-workspace omission is rejected;
- host release-gate assertion repaired;
- current release/provenance/qualification identity normalized to RC9.1;
- scheduler/executor status telemetry exposes active lease IDs;
- regression tests added for stale scheduler lease, stale physical lease, and
  omitted workspace access.

## RC9

- Native backend `QwenExecutor` ownership moved under
  `KvMemPhysicalExecutorPool`.
- Existing single-slot generation code references pool runtime 0 rather than
  owning the executor directly.
- `/v1/kvmem/executors` is sourced from the physical pool.
- Multi-slot CUDA remains fail-closed.

## RC8

- Added generic N-slot `KvMemPhysicalExecutorPool`.
- Added two-slot host qualification proving distinct ownership, simultaneous
  host leases, fault isolation, and cold recovery.

## RC7

- Added `KvMemExecutorSlotRuntime<T>` and detachable logical-session/scheduler
  ownership boundaries.

## Retained safety boundaries

- canonical session state is derived host state and can be snapshotted/rebuilt;
- physical runtime state is ephemeral and is not serialized as authority;
- scheduler affinity and physical warm state must agree;
- failed runtime state is quarantined dirty;
- multi-slot CUDA remains fail-closed;
- selected-replay persistent sessions remain unsupported;
- KVMI-012 and KVMI-002 remain explicit unresolved research/correctness items.

## Apple Silicon macOS profile

- Added `macos/qw3-mac` command wrapper with install, doctor, host-build, llama.cpp Metal, MLX, gateway, and MLX-LoRA commands.
- Added an OpenAI-compatible continual-memory gateway for local Metal/MLX inference.
- Added Darwin timestamp portability in archive identity checks.
- Added macOS logical file preallocation fallback for tier files.
- Added CMake fail-closed handling for attempts to enable CUDA on macOS.
- Added macOS GitHub CI for host/native and continual-plane tests.
- Native CUDA KVMem execution is not mislabeled as Metal-compatible; the Mac profile uses upstream model execution and retains the continual-memory/qualification system.
