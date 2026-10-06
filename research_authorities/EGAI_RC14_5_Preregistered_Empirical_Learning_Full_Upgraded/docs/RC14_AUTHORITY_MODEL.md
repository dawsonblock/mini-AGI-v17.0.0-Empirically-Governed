# RC14 Authority Model

RC14 enforces the architectural invariant:

```text
Research != Proposal != Evaluation != Qualification != Promotion != Activation
```

No proposal/ranking component has persistence authority. Privileged candidate transitions require a configured verifier for the exact destination state. StateEpoch lifecycle transitions likewise require the verifier assigned to that lifecycle boundary, allowing promotion, commit, witness, attestation, and serving keys to remain distinct.

## Candidate lifecycle

```text
REGISTERED -> BUILT -> EVALUATED -> QUALIFIED
                                     |
                                     v
                                AUTHORIZED
                                     v
                              EPOCH_PREPARED
                                     v
                                 COMMITTED
                                     v
                                  WITNESSED
                                     v
                                  ATTESTED
                                     v
                                  SERVABLE
```

Terminal/side paths include `REJECTED`, `REVOKED`, `ROLLED_BACK`, and `RETIRED`.

Every privileged transition binds the previous state and event digest, preventing a valid receipt from being transplanted onto a different candidate history.

## StateEpoch closure

`StateEpochRC14` binds all state required to reproduce one serving generation. Changing any bound component produces a different content digest and therefore requires a new epoch.

A request lease pins the serving epoch at request start. The caller should propagate the returned `ExecutionContext` instead of re-reading the global serving pointer mid-request.
