# RC10.22 Apple-Silicon qualification closure

RC10.22 does not claim that a reference Metal kernel is equivalent to a qualified production backend. It adds an explicit hardware/runtime certificate so the accelerated Qwen path can only be enabled after paired comparison with the exact selected-token replay oracle on the actual Mac that will execute it.

## Qualification identity

A certificate is bound to all of the following:

- `ExecutionIdentity` (base weights, adapters, tokenizer, architecture, position configuration, quantization, kernel ABI, recurrent implementation, tensor layout and dtypes);
- backend fingerprint;
- Apple host/runtime fingerprint (machine, macOS, Python, PyTorch, Transformers, MLX, Metal toolchain and MPS build/availability);
- the exact `BUILD_MANIFEST.json` bytes for the release under test;
- the append-only qualification-ledger head;
- quality and performance thresholds;
- the digest of the complete paired observation set.

Changing any bound item makes the certificate invalid for that runtime.

## Required evidence

Each paired case records exact and accelerated TTFT plus output-quality evidence. The default release policy requires at least 100 observations, maximum first-token KL <= 0.02, mean top-1 agreement >= 0.995, failure rate <= 1%, and median TTFT speedup >= 1.0x. These defaults are engineering gates, not research constants; change them only by issuing a new certificate with the new thresholds embedded.

The case set should cover deletion, reordering, duplication, isolated segments, long relocation, many joins, long segments and both stable and changed predecessors. Qualification should include the exact deployed Qwen model/adapters and dtype.

## Operational sequence

1. Run the accelerated and exact paths on the same adversarial cases and save `AccelerationQualificationObservation` JSON records.
2. Append the qualification run metadata to the `QualificationLedger`.
3. Run `scripts/probe_macos_qualification.py` to inspect the host/runtime identity.
4. Run `scripts/build_hardware_qualification.py` to create the certificate in a `HardwareQualificationStore`.
5. Configure the accelerated backend to advertise `requires_hardware_qualification=True` and the exact certificate digest.
6. Construct `ReconstructionRuntime` with the same qualification store, current hardware-runtime digest, release-manifest digest and ledger head.
7. Stage an accelerated adapter/cache namespace through `AdapterRegistry` using the same certificate and execution-identity digest.

The runtime and the promotion registry both fail closed if the certificate is absent, corrupted, bound to another execution identity, generated on another host/runtime, tied to another release, or no longer matches the qualification ledger.

## What this still does not prove

RC10.22 supplies the authority and promotion boundary for hardware qualification. It does not fabricate Apple-hardware evidence inside a non-macOS build environment. The actual Qwen seam-first path must still be run on the target Apple Silicon Mac before acceleration can legitimately be enabled.
