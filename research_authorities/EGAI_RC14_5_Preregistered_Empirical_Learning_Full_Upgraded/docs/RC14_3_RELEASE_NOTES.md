# RC14.3 Release Notes — Witnessed Runtime Closure

RC14.3 hardens the transition from an authorized candidate to a serving runtime. RC14.2 already required signed epoch lifecycle transitions, but witness and attestation digests could remain semantically opaque outside deployment conventions. RC14.3 makes those objects typed and independently verifiable in the canonical governed runtime.

## Authority changes

1. External witness artifacts bind the epoch digest, the exact locally committed transition head, authority-state digest, witness identity, observation time, and an independent Ed25519 receipt.
2. Runtime attestation v2 binds the epoch and witness to the foundation model, tokenizer, adapter set, isolated neural memory, execution manifest, runtime configuration, source tree, dependency lock, build provenance, target-platform policy, runtime-attestation policy, and authority state.
3. StateEpoch `ATTESTED` and `SERVABLE` transitions in `GovernedRC14System` fail closed unless these typed artifacts validate against configured independent verifier roots.
4. The serving gate re-derives witness and attestation digests from signed transition history instead of trusting mutable row metadata.
5. `request_context()` extends one lease-backed ExecutionContext across a whole logical request; nested reconstruction reuses the pinned epoch.
6. FreshTask AES keys and capability-token files must be regular, non-symlinked files with no group/other access.

## Validation

See `VALIDATION_SUMMARY.md` and `RELEASE_VALIDATION.json`. Current release: 217 active Python + 101 retained authority + 25 retained oracle + 25 portable native CTest = 368 passing tests, 0 failures.
