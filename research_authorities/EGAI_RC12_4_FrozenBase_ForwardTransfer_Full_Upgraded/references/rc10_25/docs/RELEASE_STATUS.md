# Release status — RC10.24 macOS

## Qualified in this package

- Source segments are immutable by ID and verified against persisted token SHA-256 digests.
- Every reusable execution artifact is bound to authoritative source bytes and one exact `ExecutionIdentity`.
- Arbitrary PIC uses a fixed seam-8 contract; cached recurrent tails exclude the fresh seam.
- Qwen3.5/3.6 structural capture, convolution-state separation, MRoPE reapply and structural tail reinjection are retained from RC10.21.
- Seam plans, execution traces, seam receipts, tail-injection receipts and final state-plane digests remain mandatory for accelerated acceptance.
- RC10.22 added a second independent gate: the accelerated backend can require a `AccelerationQualificationCertificate` bound to the exact execution identity, backend, host/runtime, release manifest and qualification ledger.
- Hardware qualification certificates are stored atomically and revalidated at runtime; missing/corrupt/stale certificates force exact selected replay.
- Accelerated adapter/cache namespaces cannot be staged or promoted through `AdapterRegistry` without a verified qualification certificate from a configured certificate store.
- Exact selected replay remains the permanent correctness oracle and fallback.

## Validation performed in this release environment

- 101 Python tests pass.
- RC10.22 hardware-certificate identity/substitution/tamper tests pass.
- RC10.24 qualification-suite payload binding, deployment-environment binding and deployment-handoff tamper tests pass.
- Runtime missing/stale certificate fallback tests pass.
- Accelerated registry promotion/certificate-loss tests pass.
- Paired qualification runner quality tests pass.
- Existing Qwen tail-injection, MRoPE, cache integrity, seam/execution receipt and GDN/HYPIC tests pass.
- Portable C++17 affine reference passes.
- Python wheel builds and imports from an isolated path.

## Requires validation on an actual Apple Silicon Mac

- Metal affine/GDN/HYPIC/causal-convolution shader compilation and execution.
- PyTorch MPS execution of the selected Qwen target and fallback-op coverage.
- Full fresh-seam execution followed by live-cache tail injection.
- Fresh-query/decode handoff after accelerated context assembly.
- Adversarial paired accelerated/exact qualification under the deployed model/adapters/dtype/backend.
- A passing RC10.24 version-2 hardware qualification certificate for the exact content-bound suite on the actual target host.
- Performance and unified-memory pressure at realistic context sizes.

## Production HYPIC status

Fail-closed. RC10.24 supplies the hardware-qualification authority needed to make a future Mac accelerated backend operational, but this package does not fabricate Apple-hardware evidence in the non-macOS release environment. The exact-replay backend remains the default until a target Mac produces a valid certificate.
