# Deep research audit -> implementation map

| Audit requirement | RC10.18-macOS implementation |
|---|---|
| HYPIC-style segment transform is the primary arbitrary-PIC mechanism | `runtime.py` routes arbitrary assemblies to `hypic_seam8()` |
| Transition exactness is conditional on unchanged local operators | `gdn_reference.py` explicitly tests same-input algebra only; exact replay remains separate |
| Per-layer/head state, not one global T/Z | `RecurrentTailArtifact(layer, head, ...)` |
| Explicit orientation / state layout | `TransitionOrientation` is part of the affine ABI |
| Seam must be replayed before cached tail | artifact contract stores only `tokens[seam_width:]`; backend API is seam-first |
| Adaptive seam requires different suffix tuple | unsupported geometric ladder removed; fixed seam-8 enforced |
| Causal-convolution boundary is separate state | `ConvBoundaryState`, NumPy seam replay, Metal reference kernel, and `conv_correction_rel_l2` contract |
| Source memory must survive cache invalidation | `SourceSegmentStore` is independent of `ExecutionArtifactStore` |
| Semantic facts are temporal/supersedable | `MemoryRecord.valid_from/valid_until/supersedes` |
| Neural cache is disposable and tiered | `ExecutionArtifactStore` + NVMe/DRAM/HBM tier metadata |
| Exact selected replay is oracle | `exact_selected_replay()` backend contract |
| Tail/SuffixReplay is prefix-scoped | topology router never uses it for arbitrary PIC |
| LinearKV must be a competing baseline | optional `single_state_init()` route |
| Online gate must not require oracle | `RuntimeRiskSignals` vs `OracleMetrics` separation |
| Shadow exact replay should recalibrate policy | deterministic `ShadowAuditSampler` |
| Adapter promotion invalidates old cache by default | `compare_execution_identity()` -> `REPLAY_REQUIRED` |
| Promotion should switch model/cache namespace together | `AdapterRegistry.stage_cache_namespace()` + atomic production state |
| Fast weights are hostile to reusable KVMem | `runtime_learning_state` is identity-bound; architecture docs defer fast weights |
| Facts should usually remain external memory | `MemoryWritePolicy.parameterize_score()` penalizes volatility/cache cost |
| Training examples must derive from evidence/source | `CandidateDatasetBuilder` requires verified source/evidence backing |
| Qualification must test adversarial edits | `qualification_harness.py` |
| RC9.2 native execution work should be preserved | complete prior runtime bundled in `native/kvmem-qw3-rc9.2` |
| Full-attention relocation must respect RoPE | `FullAttentionRelocationMetadata`; generic pairwise RoPE is reference-only, while Qwen artifacts use pre-RoPE keys + `MODEL_REAPPLY_PRE_ROPE` |
| Live Qwen capture must be complete per hybrid layer | `HybridModelLayout` + `HybridCaptureManifest` + `HybridCaptureBuffer` + `Qwen35TransformersLiveCapture` |
| Production acceleration must be qualification-bound | `ArtifactQualification` + runtime `requires_artifact_qualification` gate |
| Qwen GDN value-head/key-head association must match deployed implementation | grouped/repeat-interleave mapping is explicit in `KeyHeadMapping`; legacy modulo is compatibility-only |
| Qwen recurrent geometry must be identity-bound | layout digest includes linear key/value head counts, key/value dimensions and convolution kernel width |
| Relocated convolution boundary must describe the new predecessor interface | artifacts persist outgoing raw convolution-input history, not the old independent incoming history |
| Neural artifact semantics changed across RC10.17→RC10.18 | execution-artifact ABI v2 rejects v1 and requires regeneration from source tokens |

