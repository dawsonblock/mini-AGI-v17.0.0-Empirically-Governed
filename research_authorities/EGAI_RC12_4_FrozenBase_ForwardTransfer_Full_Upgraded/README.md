# EGAI / KVContinual RC12.4 — Frozen-Base Forward Transfer Qualification

Version: **12.4.0**  
Target: **Apple Silicon macOS (Darwin arm64)**
RC12.4 is the first release centered on a falsifiable continual-learning result rather than another architecture expansion: **does the system improve on unseen future task families while the base model remains byte-identical?** It retains RC12.3.1 target-Mac qualification and adds signed preregistration, encrypted hidden-task evaluation, one-time FreshTask leases, R0-R6 paired transfer statistics, foundation-retention/security gates, and signed forward-transfer receipts.

Primary criterion:

```text
P_future(E_n) > P_future(E_0)
while base_model_digest_n == base_model_digest_0
```

See `docs/RC12_4_FROZEN_BASE_FORWARD_TRANSFER.md` and `RC12_4_BUILD_STATUS.md`.


RC12.3.1 is a hardening/qualification release built on RC12.3. It keeps the frozen-model continual-learning, evidence, qualification, promotion, rollback, MLX/Metal, llama.cpp, KVMem/HYPIC and Apple performance layers, but adds an exact target-binding requirement before accelerated recurrent-state reuse may be authorized.

The qualified tuple is bound to the exact model, tokenizer, source closure, hardware/runtime profile, backend, precision, quantization, adapter set and execution policy. Changing any element requires requalification. Local evidence never self-promotes.

## Target-Mac workflow

```bash
./macos/qw3-mac install
./macos/qw3-mac doctor
./macos/qw3-mac test

./macos/qw3-mac generate-eq-prompts --out equivalence-prompts.jsonl --cases 64

# exact/baseline runtime
./macos/qw3-mac benchmark-diff \
  --endpoint http://127.0.0.1:8088/v1/chat/completions \
  --mode baseline \
  --prompts-jsonl equivalence-prompts.jsonl \
  --out exact-run.json

# separately launched accelerated runtime
./macos/qw3-mac benchmark-diff \
  --endpoint http://127.0.0.1:8089/v1/chat/completions \
  --mode accelerated \
  --prompts-jsonl equivalence-prompts.jsonl \
  --out accelerated-run.json

# For production HYPIC/KVMem qualification, attach native state/logit metrics.
./macos/qw3-mac attach-intermediate accelerated-run.json intermediate-metrics.jsonl \
  --out accelerated-run-with-intermediates.json

./macos/qw3-mac qualify-target-mac \
  --baseline-json exact-run.json \
  --accelerated-json accelerated-run-with-intermediates.json \
  --model /path/to/model-or-model-dir \
  --tokenizer /path/to/tokenizer-or-tokenizer-dir \
  --backend native-metal \
  --require-token-ids \
  --require-intermediate-metrics \
  --out target-mac-evidence.json

./macos/qw3-mac verify-target-mac target-mac-evidence.json
```

The public equivalence suite is an execution-equivalence suite, not a hidden capability benchmark. Hidden future-task evaluation remains the job of FreshTaskAuthority and the independent verification plane.

## Apple performance tools retained

- unified-memory/context planner;
- bounded persistent-memory prompt injection;
- MLX 4/8-bit conversion helper;
- optimized llama.cpp/Metal launcher with capability-detected optional flags;
- optional speculative decoding;
- streaming TTFT/decode benchmark;
- context-reuse benchmark;
- backend comparison;
- model/hardware-bound performance evidence.

## New RC12.3.1 qualification controls

- deterministic SSE transcript provenance and event-chain hashing;
- paired exact/accelerated differential bundles;
- case-ID and prompt-digest binding;
- exact output-text and optional exact token-ID gates;
- optional recurrent-state and logit error gates;
- TTFT and decode-speed gates;
- exact target runtime identity digest;
- tamper-evident qualification evidence;
- source-closure binding;
- no self-promotion from performance or equivalence evidence.

## Deliberate restrictions

RC12.3.1 does **not** enable automatic adapter promotion, learned plasticity authority, shared-weight online learning, architecture self-modification, or unqualified HYPIC/Metal recurrent-cache reuse.

See `docs/RC12_3_1_TARGET_MAC_QUALIFICATION.md` and `RC12_3_1_TARGET_MAC_BUILD_STATUS.md`.