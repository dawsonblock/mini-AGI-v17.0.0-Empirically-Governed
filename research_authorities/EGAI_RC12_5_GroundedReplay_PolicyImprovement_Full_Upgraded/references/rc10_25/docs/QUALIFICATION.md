# RC10.16 macOS Qualification

Exact selected replay under the current `ExecutionIdentity` is the reference path.

## Minimum reconstruction baselines

- `EXACT_SELECTED_REPLAY` — oracle.
- `HYPIC_SEAM8` — primary arbitrary-PIC candidate.
- `SINGLE_STATE_INIT` — LinearKV-style competing approximation.
- `EXACT_PREFIX_REPLAY` — canonical/shared-prefix path.

Tail/Suffix replay is tested only on prefix-compatible workloads until an independent arbitrary-assembly method is validated.

## Adversarial assemblies

The bundled qualification generator includes canonical, deletion, sparse selection, reordering, extreme relocation, duplication, isolated block, and reverse-ish selections. Evaluation should vary segment size, selected count, displacement, dense-vs-MoE model, adapter version, quantization, and context length.

## Measurement ladder

Measure recurrent-state relative L2 and angle, hidden-state error, attention-output error, expert-routing disagreement where applicable, first-token logit KL, top-1/top-k agreement, deterministic continuation agreement, task-score delta, TTFT, prefill cost, HBM/DRAM/NVMe footprint, transfer traffic, and exact-fallback frequency.

The product-level result to optimize is the fraction of traffic safely handled by each accelerated path at a measured task-quality budget—not a single average state-error number.

## Continual-learning promotion

A candidate adapter must bind dataset/evidence, base model, parent adapter, training configuration, produced artifact, evaluator results, and cache warm-up cost. Promotion must fail unless its cache namespace has been staged. Volatile facts should be tested in external-memory arms rather than forced into parameter memory.

## RC10.16 artifact qualification

A production artifact receipt additionally records whether same-hidden-input GDN algebra was verified, whether convolution-boundary material is complete, whether attention relocation is complete, the capture-manifest digest, the hardware/runtime fingerprint, and oracle qualification metrics. A strict accelerated backend fails closed to exact replay when this receipt is missing or incomplete.


## RC10.22 hardware qualification

Aggregate artifact qualification is no longer sufficient to enable the Mac accelerated path. RC10.22 additionally requires a host/runtime certificate when the backend advertises `requires_hardware_qualification=True`. The certificate binds exact execution identity, backend, host/runtime fingerprint, release manifest, ledger head, thresholds and paired exact-vs-accelerated observations. See `RC10_22_HARDWARE_QUALIFICATION.md`.


## RC10.24 content-bound qualification

Hardware qualification now includes a `QualificationSuiteManifest`. Each case stores a digest of the exact JSON payload used by the paired oracle run; the ordered suite digest is embedded in certificate version 2. A changed prompt/token payload, topology, segment count, release, ledger, backend or host therefore requires a new deployment binding and, where the certificate identity changes, requalification. See `RC10_23_CONTENT_BOUND_DEPLOYMENT.md`.
