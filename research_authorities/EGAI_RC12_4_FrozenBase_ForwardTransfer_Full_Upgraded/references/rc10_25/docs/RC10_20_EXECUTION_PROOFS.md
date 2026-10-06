# RC10.20 accelerated-execution proof contract

RC10.20 separates three different claims that must not be conflated:

1. **Artifact validity** — the cached neural artifact was compiled from the authoritative source bytes under the exact `ExecutionIdentity` and, where required, has an oracle qualification receipt.
2. **Schedule validity** — the backend actually executed `fresh seam -> cached tail` for every selected segment using the exact token and target-position ranges in the planner.
3. **Behavioral quality** — the accelerated result stays within the qualified divergence envelope relative to exact selected replay.

A valid `ArtifactQualification` establishes the first claim. `SeamExecutionTrace` plus `SeamExecutionReceipt` establish the second. Exact-replay qualification and shadow audits establish the third.

The runtime deliberately requires these independently. A mathematically valid artifact cannot excuse an incorrect execution schedule, and a valid schedule cannot prove end-to-end model quality.

## Receipt binding

`SeamExecutionReceipt` binds:

- `SeamFirstAssemblyPlan.digest`;
- the exact ordered artifact content digests;
- one exact execution-identity digest;
- the deterministic seam-trace digest;
- the backend fingerprint;
- receipt creation time.

Any plan substitution, artifact substitution, backend substitution, trace edit, or receipt edit fails validation and routes the request to exact selected replay.

## Persistent derived cache

`ExecutionArtifactStore(root=...)` persists disposable neural artifacts outside the authoritative source store.

The on-disk shape is:

```text
cache-root/
  objects/
    <storage-digest>.npz
  index/
    <execution-identity-digest>/
      <source-id-hash>.json
```

The object storage digest binds the neural content digest plus the attached qualification-receipt digest. This permits identical neural content to have distinct hardware/qualification evidence without changing the neural content identity itself.

A corrupt/missing object is a cache miss, not a knowledge loss. The authoritative source segment remains the reconstruction source of truth.

Use:

```bash
python scripts/audit_execution_cache.py /path/to/cache-root
```

to validate persisted indexes and objects.

## Qualification ledger

`QualificationLedger` is an append-only local JSONL hash chain. It is intended for exact-vs-accelerated observations, thresholds, benchmark identifiers, hardware/runtime fingerprints, and promotion evidence. It is tamper-evident, not a consensus system.

Artifact qualification can use the ledger's `evidence_digest()` as the evidence binding supplied to the qualification receipt.
