# Changelog

## 0.10.25 — target-Mac qualification preflight and execution handoff

- Added a fail-closed Apple-Silicon qualification preflight bound to the backend and hardware/runtime fingerprint.
- Qualification now explicitly requires Darwin arm64, native arm64 Python, PyTorch MPS build/availability, clang/CMake and the Metal toolchain; MLX can be required per backend.
- Added a tamper-evident preflight report and target-host CLI so non-Mac/off-MPS environments cannot accidentally generate production hardware evidence.
- Retained RC10.24 transactional deployment authority and RC10.23 content-bound qualification/deployment binding.

## 0.10.24 — transactional deployment authority

- Added a hash-chained, fsync-backed production promotion write-ahead log.
- Added PREPARE / COMMIT / ABORT records for promotion and rollback.
- Added self-digested production state and monotonic deployment generation.
- Added idempotent current-candidate promotion retries.
- Added fail-safe recovery for a single unresolved deployment transaction.
- Added production-state and WAL audit/recovery CLIs.
- Persist deployment-binding digest when staging via the verified accelerated namespace API.
- Retained RC10.23 content-bound hardware qualification and all fail-closed acceleration gates.

## 0.10.23 — content-bound qualification suite + target-host deployment binding

- Upgraded hardware qualification certificates to version 2 and bound them to a cryptographic `QualificationSuiteManifest`.
- Added per-case payload digests so a case ID cannot be reused with changed prompts/tokens while retaining old qualification authority.
- Reject non-finite/invalid quality and TTFT metrics before certificate construction; qualification JSON hashing now forbids NaN/Infinity.
- Expanded the Mac hardware/runtime fingerprint with hardware model, chip/CPU identity and physical-memory size.
- Hardened accelerated cache staging and promotion to verify backend fingerprint, hardware/runtime digest, release manifest, qualification-ledger head and qualification-suite digest.
- Added `AccelerationDeploymentBinding`, a tamper-evident single-object handoff for qualified accelerated deployment.
- Added target-host suite, deployment-binding build and verification CLI tools.
- Added qualification-suite and deployment-binding substitution/tamper tests; Python suite now passes 101 tests in the release environment.
- RC10.22 version-1 hardware certificates remain parseable for audit but are not reusable for accelerated execution; requalification is required.
- Production HYPIC remains fail-closed until the actual target Apple Silicon host produces passing paired exact-vs-accelerated evidence.

## 0.10.22 — Apple-Silicon hardware qualification authority + promotion gate

- Added `HardwareRuntimeFingerprint`, binding acceleration qualification to the exact Mac machine/runtime stack, including macOS, Python, PyTorch, Transformers, MLX, Metal toolchain, MPS state and backend fingerprint.
- Added paired exact-vs-accelerated qualification observations with quality and TTFT evidence.
- Added a tamper-evident `AccelerationQualificationCertificate` bound to one `ExecutionIdentity`, backend fingerprint, host/runtime fingerprint, release manifest, qualification-ledger head, thresholds and complete observation-set digest.
- Added crash-safe `HardwareQualificationStore` with digest-addressed certificates and fail-closed corruption handling.
- Hardened `ReconstructionRuntime`: an accelerated backend may now advertise `requires_hardware_qualification`; when enabled, the exact certificate must exist and match the current model, backend, host/runtime, release and ledger before HYPIC can run.
- Hardened `AdapterRegistry`: accelerated cache namespaces require a configured certificate store, certificate digest and execution-identity digest, and promotion revalidates the certificate rather than trusting staged metadata.
- Added `run_paired_oracle_qualification` for paired output/TTFT evidence generation.
- Added `probe_macos_qualification.py`, `build_hardware_qualification.py`, and `verify_hardware_qualification.py`.
- Added RC10.22 hardware qualification documentation and policy example.
- Production HYPIC remains disabled until the actual deployed Qwen/Metal path produces a passing certificate on the target Apple Silicon host.


## 0.10.21 — native Qwen tail reinjection + convolution decode-state split

- Split causal-convolution state into two explicit objects: `ConvBoundaryState` (K-1 predecessor samples for fresh-seam reconstruction) and `ConvDecodeState` (K samples required by the native single-token decode cache).
- Upgraded persisted execution artifacts to ABI v4; v1-v3 artifacts now fail closed and must be regenerated from authoritative source tokens.
- Added `HybridExecutionState` and deterministic state-plane digests covering recurrent, convolution, native convolution-decode and attention state.
- Added tamper-evident `TailInjectionReceipt` objects that bind cached-tail reinjection to exact source bytes, artifact contents, execution identity, position range and before/after state-plane digests.
- Hardened `ReconstructionRuntime`: accelerated results now require one valid tail-injection receipt per segment and a final state-plane digest matching the final receipt.
- Added model-native Qwen3.5 text MRoPE reapplication using the deployed model's own rotary-embedding object and Transformers rotary function.
- Added a structural current-Transformers Qwen3.5 cache bridge that injects recurrent `(T,Z)` tails, K-sample convolution decode state and relocated full-attention tail K/V after a fresh seam.
- Added batch-1 fail-closed shape/head coverage checks for live Qwen cache reinjection.
- Expanded the Python suite to 80 tests.
- Production HYPIC remains disabled until this injection path is exercised and exact-oracle qualified on actual Apple Silicon hardware.

## 0.10.20 — verified seam execution + persistent content-addressed cache

- Added tamper-evident `SeamExecutionReceipt` objects bound to the exact seam plan, execution identity, artifact content digests, execution trace and backend fingerprint.
- Hardened arbitrary-PIC acceptance: HYPIC results now require a valid plan-matching `SeamExecutionTrace` **and** a bound execution receipt; either failure routes to exact selected replay.
- Added deterministic trace digests so schedule evidence can be audited independently of backend-specific state objects.
- Added optional crash-safe persistent `ExecutionArtifactStore(root=...)` with atomic namespace indexes and digest-addressed NPZ objects.
- Persistent cache loads validate source ID, execution identity, serialized content digest and storage digest before returning a hit; corrupt derived cache files fail closed and are rematerializable from authoritative source tokens.
- Separated core artifact content identity from qualification-dependent storage identity, avoiding receipt recursion while allowing differently qualified copies of identical neural content.
- Added namespace eviction and garbage collection for unreferenced persisted cache objects.
- Added an append-only hash-chained qualification evidence ledger with fsync-on-append and tamper detection.
- Added `scripts/audit_execution_cache.py` for offline validation of persisted cache indexes/objects.
- Preserved RC10.19 source immutability, source-token binding, prefix-topology correction and Qwen3.5 live capture.
- Expanded the Python suite to 69 tests.
- Production Qwen HYPIC still remains fail-closed until actual seam-first full-model tail injection and Apple-Silicon oracle qualification pass.

## 0.10.19 — source-integrity + cryptographic seam execution contract

- Made `SourceSegmentStore` truly immutable by ID; conflicting replacement attempts now fail instead of silently using `INSERT OR REPLACE`.
- Added read-time token-digest verification for authoritative source rows.
- Bound every newly materialized `ExecutionArtifact` to the exact source-token digest used to compile it.
- Added execution-artifact format v3; v1/v2 artifacts fail closed and must be regenerated from source tokens.
- Bound seam-first assembly plans to source-token digest, artifact content digest and execution-identity digest.
- Added an auditable `SeamExecutionTrace` contract that rejects cached-tail-before-seam, skipped, overlapping or reordered execution schedules.
- Corrected prefix topology: a contiguous middle-of-stream span is no longer classified as an exact prefix unless it begins at canonical token position zero.
- Added prefix-checkpoint source-digest verification before checkpoint reuse.
- Expanded the Python suite to 61 tests.
- Production HYPIC remains fail-closed until real seam-first full-model injection and Apple-Silicon oracle qualification pass.

## 0.10.18 — Qwen3.5 live capture + artifact ABI correction

- Added a fail-closed structural Hugging Face Qwen3.5/3.6 live-capture adapter.
- Added real per-layer extraction of GDN key/value, decay and beta tensors from the hidden states entering the deployed layer.
- Corrected multi-head recurrent capture to Qwen grouped/repeat-interleave key-head mapping and added rectangular state support.
- Corrected convolution semantics: artifacts now persist the outgoing raw projected convolution history needed by a relocated successor seam, not the independent segment's original incoming history.
- Added pre-RoPE attention K/V capture and a model-reapply position strategy for Qwen interleaved MRoPE rather than applying the generic 1-D pairwise RoPE helper.
- Added execution-artifact format v2; v1 artifacts fail closed and must be regenerated from authoritative source tokens.
- Added exact runtime/model/layout/position identity checks to the Qwen capture CLI.
- Added `generate_execution_identity.py` and `capture_qwen35_segment.py`.
- Corrected the Metal GDN reference to use Qwen grouped key-head mapping.
- Expanded the qualification/unit suite to 57 tests.
- Production HYPIC acceleration remains disabled until seam-first full-model execution and exact-oracle qualification pass on Apple Silicon.

## 0.10.17 — live artifact pipeline + seam-first integrity

- Added a fail-closed live hybrid capture session ABI and version-pinned Transformers adapter contract.
- Added compilation of complete live captures into model-derived execution artifacts.
- Added concrete full-attention artifacts with pre-RoPE keys, values and source positions.
- Added deterministic execution-artifact content digests.
- Bound qualification receipts to execution identity, artifact content, capture manifest, hardware and qualification evidence.
- Added seam-first assembly plans and made seam-first execution a required HYPIC backend capability.
- Added plan-aware HYPIC runtime entrypoint; backends that only claim generic HYPIC now fall back to exact replay.
- Added safe pickle-free NPZ serialization/deserialization for the NVMe execution-cache tier.
- Added persisted-artifact validation CLI tooling.
- Expanded Python qualification/unit suite to 48 tests.
- Production HYPIC remains deliberately disabled in the generic Transformers/MPS backend until a version-specific Qwen adapter and Apple-hardware oracle qualification are complete.

## 0.10.16 — macOS hybrid-boundary closure

- Added hybrid model layout discovery from explicit layer types or a full-attention interval.
- Added fixed seam-8 per-layer capture manifests and a version-agnostic live capture buffer contract.
- Added RC9.2-compatible causal depthwise-convolution seam replay in NumPy.
- Added a correctness-first Metal causal-convolution seam kernel and smoke executable.
- Added RoPE-aware full-attention key relocation and relocation metadata.
- Extended execution artifacts with explicit convolution-boundary and attention-relocation state.
- Added hardware/capture-manifest-bound artifact qualification receipts.
- Changed implicit backend capabilities to fail closed for acceleration.
- Hardened arbitrary-PIC routing so HYPIC additionally requires convolution seam repair and full-attention relocation; production backends may require qualified artifacts.
- Added a Transformers config inspection script that emits the RC10 hybrid/capture manifest.
- Exact selected replay remains the correctness oracle; production Qwen hooks/fused Metal execution are still not falsely claimed complete.

## 0.10.15 — macOS GDN/HYPIC reference bring-up

- Added a fixed-input Gated DeltaNet HYPIC capture implementation that constructs dense tail `(T,Z)` summaries directly from prepared `k/v/decay/beta` inputs using the rank-1 transition identity.
- Added multi-head capture using the same `v_head % k_head_count` mapping as the bundled RC9.2 native GDN path.
- Added stable Qwen-style alpha/beta preparation with numerically stable softplus and sigmoid handling.
- Added Apple Metal correctness kernels for GDN gate preparation, one-token recurrent execution, and fixed-seam tail `(T,Z)` capture.
- Added an Objective-C++ Metal GDN/HYPIC smoke test that compares GPU-captured summaries against a CPU oracle.
- Expanded the Mac native build to compile one reference metallib containing affine and GDN/HYPIC kernels and run both smoke programs.
- Added a standalone/CLI Mac GDN reference demo and expanded release tests.
- Preserved conservative capability gating: these reference kernels do not advertise production HYPIC model integration until per-layer capture, convolution seam repair, full-attention K/V relocation, and end-to-end qualification are complete.

## 0.10.14 — macOS / Apple Silicon execution release

- Added explicit macOS/Apple Silicon platform detection and diagnostics.
- Added backend capability contracts so unsupported accelerated reconstruction cannot be selected silently.
- Added exact selected-token replay backend using Transformers + PyTorch MPS with CPU fallback.
- Added MLX-backed affine `(T,Z)` execution with NumPy fallback.
- Added Mac-specific routing: no HYPIC artifacts => exact replay, including canonical-prefix fallback when native checkpoint restore is unavailable.
- Added Apple Metal affine reference kernels for left/right transition orientation.
- Added Objective-C++ Metal smoke program and build script.
- Added macOS arm64 CMake preset with CUDA/FlashInfer disabled and the CUDA-dependent native server omitted.
- Added macOS bootstrap, native build/test, and exact-replay example scripts.
- Added Mac configuration and Apple Silicon deployment documentation.
- Preserved RC10.13 source/execution/parameter-memory separation, fixed seam-8 semantics, exact oracle, cache namespaces, and continual-learning safeguards.

## 0.10.13 — Coherent Hybrid Continual Memory research-audit upgrade

- Split authoritative `SourceSegment` data from disposable `ExecutionArtifact` state.
- Added conservative `ModelIdentity` / `ExecutionIdentity` cache validity.
- Added fixed seam-8 per-layer/head recurrent tail artifacts and removed unsupported geometric seam escalation.
- Restricted prefix replay to genuine prefix topology and retained exact selected replay as oracle.
- Added LinearKV experiment hook, shadow auditing, cache tiers and cache-aware learning promotion.
- Bundled RC9.2 native runtime and portable GDN affine reference validation.
