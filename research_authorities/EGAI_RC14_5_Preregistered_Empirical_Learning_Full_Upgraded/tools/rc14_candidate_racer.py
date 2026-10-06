from __future__ import annotations
import json, sys
from minagi.rc14.candidate_state import TransactionalCandidateStateStore

root, candidate, build_digest, actor = sys.argv[1:5]
store = TransactionalCandidateStateStore(root)
try:
    out = store.transition(candidate_digest=candidate, new_state="BUILT", actor=actor, authority_generation=1, policy_generation=1, stage_artifact_digest=build_digest)
    print(json.dumps({"ok": True, "event_digest": out["event_digest"]}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}))
