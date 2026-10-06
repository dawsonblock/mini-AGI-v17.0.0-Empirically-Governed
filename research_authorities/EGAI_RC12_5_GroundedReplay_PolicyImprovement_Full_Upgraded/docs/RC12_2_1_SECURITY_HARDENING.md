# RC12.2.1 Security Hardening

## Independent signing
Run qualification and promotion with separate Unix sockets, keys, replay databases, process identities, and purpose allow-lists. The learning plane must have no access to either private key.

## Anti-replay
Every signing request binds purpose, exact object digest, request ID, timestamp, and authority ID. Request IDs are committed to a WAL-backed SQLite replay store before signing. The same request ID remains invalid after service restart. Old and excessively future-dated requests are rejected.

## Data-plane integrity
`verify_chain()` now recomputes every stored value digest, checks tombstone digests, version continuity, previous-digest linkage, and nonempty transaction IDs. Merely preserving the previous-digest chain is not sufficient.

## Runtime activation
Pointer replacement uses write + fsync + atomic rename + parent-directory fsync. Signed activation/rollback receipts bind generation, previous runtime, previous closure, new runtime, new closure, action and time. Production mode can require a signature.

## Sandboxing
`LocalSubprocessSandbox` remains a reference resource limiter. `HardenedSubprocessSandbox` adds OS-backed network denial through `sandbox-exec` on compatible macOS hosts or `bwrap --unshare-net` on compatible Linux hosts. With `require_hardened=True`, absence of an enforceable backend aborts execution rather than silently degrading.

These mechanisms improve the reference implementation but do not by themselves prove host independence, HSM-backed key protection, or VM-grade isolation. Those remain deployment requirements for high-assurance promotion authority.
