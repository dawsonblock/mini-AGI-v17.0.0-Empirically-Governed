# Implementation notes

This source tree is intentionally small enough to falsify the architecture. It is not a production AGI system and does not contain a foundation model, trainer, GPU kernels, HYPIC implementation or autonomous architecture search.

The correct next integration point for a local model is an adapter interface in the Cognitive Plane. Preserve the base-model digest in RuntimeManifest. KVMem/HYPIC belongs in execution memory, not the evidence ledger. DeepSeek-style KV compression/conditional memory belongs below cognition and must not be confused with qualified semantic/procedural memory.
