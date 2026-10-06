# RC10.23 content-bound qualification and deployment

RC10.23 closes two authority gaps left by RC10.22.

First, a qualification certificate is now bound to the **actual qualification corpus**, not only to case names and measured outputs. Each case carries a SHA-256 digest of the JSON payload used for the paired exact/accelerated run. The ordered case descriptors form a `QualificationSuiteManifest`; its digest is embedded in the hardware qualification certificate. Reusing the same case ID with different source tokens, segment order, query, or other payload content therefore creates a different qualification identity.

Second, accelerated deployment is bound to the complete target environment before a cache namespace can be staged or promoted. The registry now verifies the certificate against:

- exact execution identity;
- backend fingerprint;
- target hardware/runtime digest;
- release-manifest digest;
- qualification-ledger head;
- qualification-suite digest.

`AccelerationDeploymentBinding` packages those values into one tamper-evident handoff object. This avoids manually copying several digests between qualification and deployment steps.

## Mac hardware fingerprint

The RC10.23 fingerprint retains the RC10.22 software/runtime fields and additionally binds the certificate to:

- `hw.model` on macOS;
- Apple chip/CPU identity;
- physical memory size.

A certificate from a materially different Mac host class is therefore not silently accepted as evidence for another host.

## Recommended target-Mac workflow

Build a content-bound suite:

```bash
python scripts/build_qualification_suite.py \
  --cases-json configs/qualification_cases.example.json \
  --name qwen35-hostile-v1 \
  --out qualification-suite.json
```

Run the exact and accelerated implementations against those exact cases and save `observations.json`. The observation order, topology and segment count must match the suite manifest.

After recording the qualification event in the append-only ledger, build the certificate:

```bash
python scripts/build_hardware_qualification.py \
  --identity-json configs/execution_identity.example.json \
  --backend-fingerprint qwen35-metal-v1 \
  --release-manifest BUILD_MANIFEST.json \
  --observations-json observations.json \
  --suite-manifest qualification-suite.json \
  --ledger qualification.jsonl \
  --store qualification-certificates
```

On the target Mac, create the deployment binding from that certificate:

```bash
python scripts/build_deployment_binding.py \
  --certificate qualification-certificates/<digest>.json \
  --backend-fingerprint qwen35-metal-v1 \
  --release-manifest BUILD_MANIFEST.json \
  --suite-manifest qualification-suite.json \
  --ledger qualification.jsonl \
  --out deployment-binding.json
```

The command probes the *current* Mac and refuses to emit a binding if the certificate belongs to another hardware/runtime fingerprint, release, suite or ledger state.

Verify the handoff independently:

```bash
python scripts/verify_deployment_binding.py \
  deployment-binding.json \
  qualification-certificates/<digest>.json
```

Application code can then load the binding and call `AdapterRegistry.stage_accelerated_cache_namespace(...)`. Promotion rechecks the certificate again, so deleting, corrupting or substituting qualification evidence after staging still fails closed.

## Certificate version

RC10.23 uses hardware qualification certificate version 2. RC10.22 version-1 certificates can still be parsed for audit purposes, but they are not reusable for accelerated execution because they are not bound to a qualification suite digest. Requalification is required.

## Numerical evidence hygiene

Qualification metrics are now required to be finite. NaN, infinity, negative KL values, top-1 agreement outside `[0,1]`, and negative TTFT measurements are rejected before a certificate can be constructed. Canonical JSON digest generation also disables non-standard NaN/Infinity serialization.

## Production status

This is an authority and reproducibility upgrade. It does not fabricate a successful Qwen/Metal qualification run. Production HYPIC remains fail-closed until the actual target Apple Silicon machine produces passing paired exact-vs-accelerated evidence for the exact release and execution identity.
