# Upgrade Notes — v15.4.0

Use `minagi.v15` as the production Python import surface. RuntimeClosure1 does not add promotion authority; it strengthens the native serving boundary around the existing StateEpoch/adapter path.

## Required governed-serving roots

In addition to the v15.3 epoch/manifest/adapter arguments, governed QW3 now requires component roots for:

- `--state-foundation-digest`
- `--state-tokenizer-digest`
- `--state-kvmem-archive-root`
- `--state-retrieval-policy-root`
- `--state-skill-policy-root`
- `--state-runtime-binary-digest`

`MeasuredRuntimeClosure.from_files(...)` derives the physically measurable roots from the model, the exact QW3 executable that will be deployed, and the optional KVMem archive. Its `qw3_args()` method emits the complete governed component-root argument set.

At native startup QW3 independently measures its running executable via the process executable path; it does not trust a caller-supplied binary pathname. It recomputes the canonical artifact root and refuses startup if the supplied aggregate identity is inconsistent.

For an absent KVMem archive, `kv_archive_root` must be 64 zeroes. For a present archive, it is the SHA-256 of the sealed archive `manifest.json`.

See `docs/RUNTIME_CLOSURE_V15_4.md`.

---

# Upgrade Notes — v15.3.0

Use `minagi.v15` as the production Python import surface. v15.3 preserves the alpha5/v15.2 authority and qualification chain; it does not introduce a second promotion path.

## Native adapter serving contract

A governed QW3 process serving a native adapter now binds:

- `--state-epoch-id`
- `--state-manifest-digest`
- `--state-artifact-root`
- `--state-adapter-set-root`
- `--state-native-adapter-bundle-root`
- `--native-adapter-bundle <directory>`

The Python `GovernedServingContract` supplies the corresponding request identities, including `X-MiniAGI-Native-Adapter-Bundle-Root` when a native bundle is present. QW3 rejects mismatches before generation.

## NativeAdapter1 scope

`NativeQW3AdapterCompiler` accepts only a qualified adapter artifact whose entire LoRA content is representable as LM-head/output low-rank matrices. Unsupported layer adapters are rejected. The native bundle is bound to the exact qualified adapter-set root, raw model SHA-256, foundation digest, qualified-candidate digest, and individual A/B payload digests.

The QW3 native path applies `scale * B * (A * normalized_hidden)` to logits. This release does not claim all-linear LoRA, CUDA qualification, real-weight task improvement, or long-horizon continual-learning stability.

See `docs/NATIVE_ADAPTER_V15_3.md`.
