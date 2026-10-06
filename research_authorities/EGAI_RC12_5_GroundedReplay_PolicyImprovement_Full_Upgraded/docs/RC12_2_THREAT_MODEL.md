# RC12.2 Threat Model Additions

The release explicitly tests or mitigates benchmark generation reuse across restarts, replay future-information leakage, stale derived-state writes, signer request replay, unauthorized network capability in the reference subprocess sandbox, evidence/graph confusion, capability regression, premature adapter escalation, and unqualified meta-learning from sparse records.

The local subprocess sandbox is not a hardened VM/container network sandbox. Production deployment still requires an OS/VM isolation backend with independently verified network and filesystem enforcement.
