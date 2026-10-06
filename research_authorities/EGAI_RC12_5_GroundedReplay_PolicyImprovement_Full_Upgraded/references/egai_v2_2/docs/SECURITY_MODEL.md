# Security / Integrity Model

Threats: poisoned observations, replay leakage, forged qualification, manifest substitution, artifact traversal, model-generated evidence laundering, hidden-task leakage, unauthorized persistent mutation, benchmark overfitting.

Controls implemented in v2.1:
- authoritative evidence admission checks;
- append-only hash chains;
- sha256 content-addressed artifact store with strict digest parser;
- Ed25519 qualification/promotion receipts;
- exact digest-bound manifest chain;
- persistent derived-state commit capability held only by PromotionAuthority;
- structural replay prefix visibility;
- FreshTaskAuthority single-release interface;
- fail-closed L6-L9 plasticity.

Not yet implemented: OS-level process isolation, key custody/HSM, remote attestation, multi-host UID separation, network policy, full adversarial sandboxing. Those belong in later hardening releases.
