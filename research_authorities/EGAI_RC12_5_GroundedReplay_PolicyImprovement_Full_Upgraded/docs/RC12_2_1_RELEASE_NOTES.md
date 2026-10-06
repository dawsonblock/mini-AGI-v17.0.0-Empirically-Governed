# RC12.2.1 Authority & Integrity Hardening

RC12.2.1 is deliberately not a feature-expansion release. It makes RC12.2 harder to mis-qualify or ambiguously deploy.

Added or changed:
- one canonical release identity (`12.2.1`) across root VERSION, package metadata, and `kvcontinual.__version__`;
- generated `runtime/build`, `runtime/dist`, and egg-info copies removed from the trusted distribution;
- canonical source-closure manifest excludes historical `references/` and other derived/cache trees;
- signer services now have purpose-scoped authority, timestamp windows, and SQLite/WAL anti-replay state that survives restart;
- governance data-plane schema v2 adds transaction IDs, `BEGIN IMMEDIATE` writes, migration from v1, full digest recomputation, sequence checking, and whole-store verification;
- runtime activation and rollback now fsync the parent directory and can require Ed25519-signed receipts in an append-only audit file;
- production sandbox mode now fails closed when no enforceable OS-backed network-denial backend is available;
- qualification and promotion signers can be instantiated as distinct services with non-overlapping allowed purposes.

Still deliberately disabled:
- automatic adapter promotion;
- learned plasticity authority;
- model-predicted outcomes as evidence;
- shared-weight self-modification;
- architecture self-modification;
- production Metal/HYPIC authorization without target-Apple-Silicon differential qualification.
