# RC9.1 Validation Report

Qualification date: 2026-10-04

## Final host qualification

- `python3 scripts/release/source_audit.py`: **PASS**
- `python3 scripts/release/verify_manifest.py`: **PASS**
- `bash scripts/release/host_gate.sh`: **PASS**
- CMake host build: **PASS**
- CTest: **19/19 PASS**
- `python3 -m pytest -q scripts/kvmem_eval/test_*.py`: **9/9 PASS**
- TypeScript adapter check (`tsc --noEmit ... examples/nemo/qw3_kvmem_runtime.ts`): **PASS**

## Correctness regressions covered

- stale logical scheduler lease cannot release a newer lease for the same session;
- stale physical executor token cannot release a newer physical owner;
- physical token namespace remains independent from scheduler lease IDs;
- physical runtime records the scheduler lease that caused a persistent bind;
- stale physical token cannot perform a cold-reset transition;
- omitted workspace ID cannot bypass an existing workspace binding;
- dirty executor lineages still require cold recovery before warm reuse;
- multi-slot native CUDA remains fail-closed.

## ABI change

Physical executor runtime status is now `executor-slot-runtime-v2`.

New/strengthened telemetry:

- scheduler slot `active_lease_id`;
- physical runtime `active_lease_id`;
- physical runtime `lease_sequence`;
- physical runtime `linked_scheduler_lease_id`.

## CUDA qualification

**NOT RUN / NOT CLAIMED.**

The artifact-generation environment did not provide the target NVIDIA GPU and
compatible model weights required by `scripts/release/gpu_gate.sh`. Therefore
this package does not claim:

- CUDA kernel qualification for RC9.1;
- real-model executor lifecycle qualification;
- multi-slot CUDA execution;
- multi-executor archive/tier/device fault isolation;
- production performance on a target GPU.

## Remaining known research/correctness limitations

- KVMI-012: attention selection and DeltaNet/recurrent-state history coherence
  remains unresolved for the broader persistent hybrid-memory case.
- KVMI-002: partial-block retrieval-index parity remains open.
- persistent selected-replay remains unsupported.
- continuous-batching auxiliary executors are not represented as independently
  certified KVMem pool slots.

RC9.1 should therefore be treated as a host-qualified correctness release for
the one-slot native ownership/control plane, not as a completed multi-GPU or
fully coherent hybrid-memory production release.
