# RC10 macOS compatibility validation

Release profile: Apple Silicon compatibility layer.

Implemented:

- host-source portability for Darwin stat timestamps;
- macOS logical NVMe-tier file sizing fallback;
- CMake fail-closed behavior when CUDA is requested on macOS;
- macOS host build script and GitHub macOS CI workflow;
- OpenAI-compatible local inference client;
- llama.cpp/Metal launcher;
- MLX launcher;
- persistent-memory OpenAI-compatible gateway;
- explicit memory endpoints and episode logging;
- MLX LoRA/QLoRA training command adapter;
- Apple Silicon doctor utility.

Local artifact-generation validation:

- native Linux host regression suite: 20/20 passed after portability changes;
- continual/control-plane suite: 21/21 passed;
- source audit: required before packaging;
- macOS hardware execution: cannot be run in the Linux artifact-generation environment and remains a target-machine qualification step.

The release does not claim native Metal parity with the CUDA KVMem engine. On macOS, model execution is delegated to an upstream Metal/MLX backend while the persistent continual-learning plane runs locally.
