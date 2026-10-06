# RC12.4 Apple Silicon / Target-Mac Qualification + Frozen Transfer

RC12.4 retains the RC12.3.1 target-Mac qualification stack and adds a stricter differential-qualification path for accelerated execution. Portable validation does not prove Metal correctness. Production HYPIC/KVMem acceleration must be qualified on the exact target Mac.

## Recommended sequence

1. `./macos/qw3-mac install`
2. `./macos/qw3-mac doctor`
3. `./macos/qw3-mac test`
4. `./macos/qw3-mac apple-profile ...`
5. run baseline MLX or llama.cpp/Metal; measure `benchmark-perf`;
6. run the accelerated candidate separately;
7. generate deterministic equivalence prompts and capture paired `benchmark-diff` bundles;
8. for HYPIC/KVMem, attach native recurrent-state/logit metrics;
9. run `qualify-target-mac`;
10. independently bind/sign the evidence and runtime closure before enabling acceleration.

The gateway's persistent memories remain derived context, not authoritative evidence. Adapter changes invalidate execution-cache assumptions and require requalification.

## Important limitations

The build-generation host is not an Apple Silicon Mac, so it cannot claim measured target-Mac TTFT, real Metal-kernel execution, or HYPIC equivalence on the final model. Those are explicit target-machine gates.
