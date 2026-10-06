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
