# RC10.24 Transactional Deployment Authority

RC10.24 adds a write-ahead authority layer around model + cache namespace promotion. The objective is narrow: a crash, partial write, operator retry, or tampered production pointer must not silently change which model/cache namespace is authoritative.

## Invariant

A production pointer is accepted only when all three statements are true:

1. `production.json` is self-digested and has not been modified after it was written.
2. the promotion WAL is a valid append-only SHA-256 hash chain;
3. the installed production state is exactly the after-state of the latest committed WAL transaction, with no unresolved PREPARE record.

Qualification certificates and deployment bindings remain the authority for whether an accelerated namespace is eligible. RC10.24's WAL is a separate authority for whether an eligible namespace actually became production state.

## Transaction sequence

Promotion and rollback use the same protocol:

```text
validate candidate / qualification / namespace
        ↓
PREPARE(before_state, after_state) + fsync
        ↓
install production.json atomically + fsync
        ↓
COMMIT(after_state_digest) + fsync
```

If the transition raises inside the process, RC10 restores the prior production pointer and appends ABORT. If a process or host dies after PREPARE, `recover_production_state.py` fails safe by restoring the PREPARE record's before-state and appending ABORT. It never guesses that an uncommitted after-state is safe.

## Idempotence

Retrying promotion of the already-current candidate with the identical staged cache namespace is a no-op. It does not increment the generation and does not add another WAL transaction.

## Audit

```bash
python scripts/audit_production_state.py --registry ./registry
```

This verifies the production-state self-digest, the full WAL hash chain, transaction pairing, absence of unresolved transactions, and equality between the installed state and the latest committed after-state.

## Recovery

```bash
python scripts/recover_production_state.py --registry ./registry
```

Automatic recovery is intentionally limited to one unresolved PREPARE whose before/after state can be reconciled with the installed pointer. Multiple unresolved transitions or an unrelated production state require manual intervention.

## Generation

Every committed PROMOTE or ROLLBACK advances `generation`. Generation is operational history, not model identity. Cache compatibility still derives from `ExecutionIdentity` and the qualified namespace binding.
