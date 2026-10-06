# macOS / Apple Silicon build status — RC12.5

Target: Darwin arm64 / Apple Silicon.

RC12.5 retains the RC12.3.1 MLX/Metal, llama.cpp/Metal, KVMem/HYPIC differential qualification, performance evidence, context-reuse benchmarking and target-runtime binding. The new grounded replay policy layer is backend-independent.

Production authorization for recurrent-state reuse remains blocked until the exact model, tokenizer, adapter set, runtime build and target Mac pass differential equivalence against exact replay.

Run the existing target-Mac qualification commands on the actual Mac before authorizing accelerated HYPIC/KVMem execution.
