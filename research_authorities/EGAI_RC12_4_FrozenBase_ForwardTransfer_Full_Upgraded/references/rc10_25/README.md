# KVContinual RC10.24 macOS — Transactional Qualified Deployment

RC10.24 is the Apple Silicon research/engineering build of the coherent hybrid execution-memory and controlled continual-learning architecture.

The core invariants are unchanged:

> Authoritative source tokens are durable truth-bearing input. Neural execution artifacts are derived, disposable, model-versioned acceleration state.

> Arbitrary segment reuse is seam-first: execute each leading seam under the new predecessor, then inject only the cached tail.

> No accelerated result is accepted unless its source bytes, execution identity, artifact contents, seam schedule, backend receipts, tail state transitions and hardware qualification all agree. Otherwise RC10 falls back to exact selected replay.

## What RC10.24 adds

RC10.24 keeps RC10.23's content-bound hardware qualification and adds crash-safe production authority around model/cache promotion.

New pieces include:

- an append-only SHA-256 hash-chained promotion write-ahead log;
- PREPARE / COMMIT / ABORT transaction records for both promotion and rollback;
- self-digested, monotonically generated `production.json` state;
- fsync-backed atomic production-pointer writes;
- idempotent retry of an already-current promotion;
- fail-safe recovery of a single prepared-but-uncommitted transition;
- audit tooling that proves the installed production pointer matches the latest committed WAL state;
- accelerated namespace records that persist the RC10.23 deployment-binding digest when staged through the verified binding API;
- 108 Python tests in this release environment.

RC10.23's exact qualification-suite binding, hardware certificate v2, deployment binding, Qwen tail-injection receipts, CAS execution cache and exact-replay fallback are retained.

## macOS execution status

### Usable now

- immutable/versioned source and semantic memory;
- exact `ModelIdentity` / `ExecutionIdentity` namespaces;
- exact selected-token replay through Transformers + PyTorch MPS with CPU fallback;
- Qwen3.5 structural capture into derived execution artifacts;
- fixed-input GDN/HYPIC algebra and Metal reference kernels;
- distinct K-1 seam convolution state and K-sample native decode state;
- pre-RoPE attention capture and model-native text MRoPE reapplication bridge;
- structural current-Transformers Qwen tail reinjection;
- persistent integrity-checked derived cache;
- seam, execution and tail-injection receipts;
- persistent hardware qualification certificates;
- acceleration/promotion gates bound to exact Mac/runtime evidence;
- exact-replay fallback whenever any bound identity or proof does not match.

### Still not claimed complete

The generic Mac backend still does **not** advertise production HYPIC acceleration by default. RC10.23 now supplies the authority and content-binding mechanisms needed to enable it safely, but the actual deployed Qwen accelerated backend must still be run and qualified on the target Apple Silicon host.

The required final deployment sequence is:

1. run fresh-seam Qwen execution and cached-tail reinjection on the actual Mac;
2. run adversarial paired accelerated/exact cases under the exact production model, adapter set, dtype and backend;
3. record the qualification run in the append-only ledger;
4. build a passing RC10.24-compatible hardware qualification certificate bound to the exact suite;
5. bind the backend and accelerated cache namespace to that certificate;
6. only then allow the HYPIC capability bit to become operational.

Any model, adapter, runtime, backend, release-manifest, qualification-suite, ledger or host/runtime change invalidates that certificate for the new execution environment.

## Quick start

```bash
./scripts/setup_macos.sh
source .venv/bin/activate
python -m pytest -q
./scripts/build_macos_native.sh
python scripts/validate_release.py
```

Inspect the Mac/runtime qualification identity:

```bash
python scripts/probe_macos_qualification.py \
  --backend-fingerprint qwen35-metal-v1
```

Build the content-bound qualification suite first:

```bash
python scripts/build_qualification_suite.py \
  --cases-json configs/qualification_cases.example.json \
  --name qwen35-hostile-v1 \
  --out qualification-suite.json
```

After running paired exact/accelerated inference for those cases and recording the qualification ledger:

```bash
python scripts/build_hardware_qualification.py \
  --identity-json configs/execution_identity.example.json \
  --backend-fingerprint qwen35-metal-v1 \
  --observations-json observations.json \
  --suite-manifest qualification-suite.json \
  --ledger qualification.jsonl \
  --store qualification-certificates
```

Then create the target-host deployment binding:

```bash
python scripts/build_deployment_binding.py \
  --certificate qualification-certificates/<digest>.json \
  --backend-fingerprint qwen35-metal-v1 \
  --suite-manifest qualification-suite.json \
  --ledger qualification.jsonl \
  --out deployment-binding.json
```

See `docs/RC10_23_CONTENT_BOUND_DEPLOYMENT.md`, `docs/RC10_22_HARDWARE_QUALIFICATION.md`, `docs/MACOS_APPLE_SILICON.md`, `docs/INTEGRATION_QWEN_HYBRID.md`, `docs/QUALIFICATION.md`, and `docs/RELEASE_STATUS.md`.
