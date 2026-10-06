# RC10.16 macOS Architecture

## Authority hierarchy

`SourceSegment` is authoritative for text/tokens. `SemanticMemory` is durable but temporal and supersedable. `ExecutionArtifact` is compiled state for one `ExecutionIdentity`. `LearningArtifact` is a candidate/promoted parameter change.

No derived hidden state, KV tensor, recurrent state, transition, convolution buffer, or checkpoint can override its source/evidence record.

## Recurrent tail contract

For one GDN layer/head and a fixed seam `w=8`, an artifact stores a tail map over only `C[w:]`:

`S_out = T_tail @ S_after_fresh_seam + Z_tail`

for the RC9.2 column-state orientation. The seam tokens are recomputed under the newly assembled predecessor and are therefore excluded from the cached tail tuple.

This fixes the previous unsafe pattern:

`compose whole block -> repair afterward`

The correct order is:

`new predecessor -> fresh seam -> cached tail`.

## Why adaptive seams are disabled initially

A tuple for `C[8:]` cannot be reused after replaying `C[:32]` without double-processing `C[8:32]`. Supporting multiple seam widths requires separate suffix tuples, a range-composable transition representation, or replay. RC10.16-macOS preserves fixed seam-8 plus replay escalation until data justifies more complexity.

## Topology-aware reconstruction

Arbitrary assembly uses HYPIC-style seam-8 reconstruction. Genuine shared-prefix continuation uses exact checkpoints. Prefix-reconstruction research methods are intentionally not routed into arbitrary transplantation by default.

## Runtime risk vs oracle metrics

Online risk features are cheap quantities available from the seam: hidden disagreement with the original boundary anchor, attention-output disagreement, route disagreement, convolution correction magnitude, join count, displacement, and historical failure rate.

Oracle metrics—state error, hidden error, KL, top-k agreement, task-score delta—require exact selected replay and are used offline or on sampled shadow audits. They are not silently computed on every request.

## Cache namespaces under learning

An adapter promotion creates a new execution identity and a new cache namespace. Hot artifacts can be prebuilt for the candidate namespace before promotion. Promotion atomically switches model + cache namespace. Rollback switches both back.

Fast weights are intentionally deferred because changing projections inside cached computation would namespace or invalidate the cache at session timescales.

## Boundary-state closure in RC10.16

`ConvBoundaryState` makes the pre-GDN causal-convolution history explicit. `FullAttentionRelocationMetadata` records whether attention keys are already RoPE-rotated or pre-RoPE. The runtime therefore has concrete contracts for the two state planes that were previously implicit. A production accelerated backend must advertise both causal-convolution seam repair and full-attention relocation; otherwise arbitrary PIC falls back to exact selected replay.

## Capture manifests and qualification

A `HybridCaptureManifest` is derived from the model layout and seam width. A live model integration must populate `HybridCaptureBuffer` for every required GDN and full-attention layer. Production backends may require `ArtifactQualification` receipts bound to the capture-manifest digest and hardware/runtime fingerprint.
