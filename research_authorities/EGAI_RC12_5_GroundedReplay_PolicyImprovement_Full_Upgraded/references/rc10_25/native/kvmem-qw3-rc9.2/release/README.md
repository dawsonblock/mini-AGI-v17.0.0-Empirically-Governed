# Hardening RC9.2 release notes

RC9.2 closes the deterministic correctness and release-integrity defects found in
the RC9/RC9.1 audit while preserving fail-closed boundaries for unqualified CUDA
and unresolved hybrid-state research.

## What changed

- Exact scheduler and physical-runtime lease fencing remains mandatory.
- Workspace-bound public session lookup rejects wrong or omitted workspace IDs.
- Trusted backend maintenance uses an explicit internal lookup so snapshots of a
  bound session remain possible without weakening the public contract.
- Generated tokens now update prompt/response boundary mean-key blocks by exact
  incremental merge; contiguous sub-block mean indexes use the same mechanism.
- ExactMass no longer consumes dynamic shared memory proportional to logical
  block count; a >12K-block CUDA regression is included.
- ExactMass fp32 raw-key allocation is bounded by
  `--kvmem-exactmass-raw-key-max-mib` (8192 MiB default; 0 disables the cap) and
  fails before allocation on overflow/cap violation.
- `/v1/kvmem/executors` declares `scope=persistent-session-runtime`; transient
  continuous-batching executors are intentionally outside the session-affinity
  pool.
- Release provenance, source audit, schemas, docs, and qualification records are
  synchronized to RC9.2.

## Certification boundary

The native backend still certifies exactly **one** CUDA persistent-session
executor slot. `--kvmem-executor-slots >1` remains fail-closed until target-GPU
multi-executor ownership/fault-isolation qualification exists.

Persistent selected-replay for an above-budget hybrid DeltaNet session remains
unsupported. One-shot selected-replay is the coherent rebuild strategy; sparse
attention-KV reselection cannot in general erase/reorder DeltaNet recurrent
history exactly.

Host qualification and target-GPU qualification are separate. This artifact may
be host-qualified without claiming that its CUDA-dependent changes ran on a GPU.

Inspection endpoints:

- `GET /v1/kvmem/status`
- `GET /v1/kvmem/scheduler`
- `GET /v1/kvmem/executors`
- `GET /v1/kvmem/resources`
- `GET /v1/kvmem/sessions`

See `docs/RC9_2_FULL_HARDENING.md`, `docs/kvmem_known_issues.md`, and
`release/RC9_2_QUALIFICATION.json`.
