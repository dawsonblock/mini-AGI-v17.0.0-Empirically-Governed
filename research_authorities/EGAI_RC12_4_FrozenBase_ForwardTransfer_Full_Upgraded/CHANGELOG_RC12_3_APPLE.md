# RC12.3 Apple Silicon changelog

## Performance
- Added conservative unified-memory/context planner.
- Added persistent-memory token budgeting to reduce prefill growth.
- Added streaming TTFT and decode-throughput benchmark.
- Added feature-detected llama.cpp optional performance arguments.
- Added explicit draft-model speculative decoding gate.
- Added MLX quantization helper with capability detection.

## Correctness / governance
- Preserved frozen-base and independent promotion boundaries.
- Preserved fail-closed HYPIC/Metal production gate.
- Added target hardware/model-bound performance evidence manifest.
- Kept performance evidence non-authoritative until independent qualification.

## Apple install fixes
- Standardized installation and verification on `.venv-mac`.
- Fixed stale integration-smoke release identity.
- Updated Apple capability reporting to prefer native MLX/Metal when available.
