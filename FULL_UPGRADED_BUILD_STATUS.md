# Full Upgraded Build Status — v15.4.0

Status: **validated measured-runtime-closure research build**.

The archive retains the v15.3 governed native LM-head LoRA path and closes a more fundamental serving-integrity gap: QW3 now derives physical identity from what it actually runs/loads rather than trusting the aggregate StateEpoch artifact root supplied by the launcher. The native server measures the foundation model, current executable and KVMem manifest, recomputes the canonical aggregate served-artifact root, exposes a runtime-closure digest, and refuses governed startup on mismatch.

This materially strengthens the meaning of `SERVABLE`: matching request headers are no longer sufficient if the process bytes or measured model/memory bytes differ.

Remaining boundaries are explicit: tokenizer/retrieval/skill-policy roots are aggregate-bound but not yet independently materialized by the native engine; native LoRA is still LM-head-only; CUDA was not available for qualification; no real-weight unseen-task improvement or long-horizon continual campaign is attached.
