# RC12.3.1 Target-Mac Qualification Protocol

## Objective

Authorize accelerated Apple execution only after the accelerated runtime is shown to match the exact/baseline runtime closely enough on the exact deployment tuple and to deliver the preregistered performance benefit.

The tuple binds:

- base model weights;
- tokenizer;
- source closure;
- hardware/runtime profile;
- backend implementation;
- precision;
- quantization;
- adapter set;
- execution policy.

Any material change invalidates the old qualification.

## Evidence classes

### 1. Public deterministic equivalence suite

Use `generate-eq-prompts` and `benchmark-diff` to exercise deterministic prompts under temperature 0. This suite measures execution equivalence, not general intelligence.

### 2. Native intermediate metrics

For production HYPIC/KVMem recurrent-state reuse, output-text equality is insufficient. Capture native paired metrics per case and attach them to the accelerated run:

- `state_max_abs_error`;
- `logit_max_abs_error`;
- exact `output_token_ids` where available.

Use `attach-intermediate` to bind these case-by-case.

### 3. Performance evidence

Measure TTFT, decode throughput and context-reuse behavior. Context-reuse benchmarks are diagnostic unless the backend's actual cache-hit/reuse metadata is independently bound.

## Minimum production matrix

The final Apple qualification suite should include canonical and adversarial cases across:

- short and long contexts;
- randomized segmentation;
- seam positions;
- repeated blocks;
- non-contiguous blocks;
- reordered blocks;
- cold and warm cache states;
- different recurrent-state lengths;
- different batch sizes;
- adapter changes;
- quantization variants;
- boundary and Unicode/tokenization cases.

A production run should use substantially more than the example minimum; the CLI default is intentionally conservative but not a scientific guarantee.

## Gates

The evidence object records independent gates for:

- sufficient paired case count;
- exact case-set and prompt-digest binding;
- exact assistant-text fraction;
- exact token-ID fraction when required;
- recurrent-state error when required;
- logit error when required;
- median TTFT ratio;
- median decode speedup.

All local gates may pass and the result still remains non-authoritative. Promotion requires the independent verification/promotion authority to bind/sign the exact runtime closure.

## Separation from continual-learning evaluation

This qualification answers: **is accelerated execution equivalent enough to exact execution on this deployment tuple?**

It does not answer: **did the system learn transferable new capability?** Hidden future-task evaluation remains separate under FreshTaskAuthority and forward-transfer qualification.
