from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kvcontinual.execution.authority import Ed25519ReceiptSigner
from minagi.egai.canonical import sha256_json
from minagi.egai.evidence import EvidenceLedger, TrustedEvidenceIngestor
from minagi.egai.models import (
    Belief,
    EvidenceOrigin,
    PromotionVerdict,
    SkillManifest,
)
from minagi.egai.skills import SkillRepository
from minagi.egai.beliefs import BeliefRepository
from minagi.state_epoch import StateEpoch, StateEpochRegistry


def _approval(signer, candidate_digest: str, qualification: str | None = None):
    q = qualification or sha256_json({"qualification": candidate_digest})
    return signer.issue({
        "schema": "mini-agi-egai-promotion-authorization-v2",
        "candidate_digest": candidate_digest,
        "qualification_digest": q,
        "verdict": PromotionVerdict.APPROVE.value,
    })


def _skill(skill_id: str, version: int, impl: str) -> SkillManifest:
    return SkillManifest(
        skill_id=skill_id,
        version=version,
        name=f"{skill_id}-v{version}",
        implementation_digest=sha256_json({"impl": impl}),
        activation_conditions=("always",),
        preconditions=(),
        contraindications=(),
        permissions=("read",),
        resource_budget={"tokens": 32.0},
        termination_conditions=("done",),
        verifier_digest=sha256_json({"verifier": "unit"}),
        supporting_evidence=(sha256_json({"evidence": impl}),),
    )


def _belief(belief_id: str, statement: str) -> Belief:
    return Belief(
        belief_id=belief_id,
        statement_digest=sha256_json({"statement": statement}),
        supporting_evidence=(sha256_json({"evidence": statement}),),
        contradicting_evidence=(),
        confidence=0.9,
        production_identity_digest=sha256_json({"runtime": "rc13"}),
    )


def test_concurrent_evidence_writers_are_unambiguous(tmp_path):
    root = str(tmp_path / "evidence")
    repo = Path(__file__).resolve().parents[1]
    helper = repo / "tools" / "rc13_evidence_writer.py"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src-python") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    procs = [
        subprocess.Popen([sys.executable, str(helper), root, str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        for i in range(12)
    ]
    results = []
    for p in procs:
        out, err = p.communicate(timeout=30)
        assert p.returncode == 0, err
        results.append(json.loads(out))
    assert len({r["digest"] for r in results}) == 12
    ledger = EvidenceLedger(root)
    status = ledger.verify()
    assert status["records"] == 12
    assert status["promotion_eligible"] == 12


def test_skill_same_version_conflict_is_rejected_and_history_preserved(tmp_path):
    repo = SkillRepository(tmp_path / "skills")
    signer = Ed25519ReceiptSigner.generate(key_id="promotion")
    verifier = signer.verifier()

    first = _skill("normalize", 1, "impl-a")
    repo.register_candidate(first)
    promoted_first = repo.promote(first.digest, _approval(signer, first.digest), verifier)

    conflict = _skill("normalize", 1, "impl-b")
    repo.register_candidate(conflict)
    with pytest.raises(RuntimeError, match="conflicting promoted skill revision"):
        repo.promote(conflict.digest, _approval(signer, conflict.digest), verifier)

    assert repo.load_active("normalize").digest == promoted_first.digest
    assert repo.load_promoted("normalize", 1).digest == promoted_first.digest

    second = _skill("normalize", 2, "impl-b")
    repo.register_candidate(second)
    promoted_second = repo.promote(second.digest, _approval(signer, second.digest), verifier)
    assert promoted_second.version == 2
    assert repo.load_promoted("normalize", 1).digest == promoted_first.digest
    assert repo.load_active("normalize").digest == promoted_second.digest
    assert repo.verify()["revisions"] == 2


def test_belief_revisions_remain_addressable_after_head_moves(tmp_path):
    repo = BeliefRepository(tmp_path / "beliefs")
    signer = Ed25519ReceiptSigner.generate(key_id="promotion")
    verifier = signer.verifier()

    a = _belief("fact-x", "alpha")
    repo.register_candidate(a)
    pa = repo.promote(a.digest, _approval(signer, a.digest), verifier)

    b = _belief("fact-x", "beta")
    repo.register_candidate(b)
    pb = repo.promote(b.digest, _approval(signer, b.digest), verifier)

    history = repo.history("fact-x")
    assert history == (pa.digest, pb.digest)
    assert repo.load_revision(pa.digest).statement_digest == pa.statement_digest
    assert repo.load_promoted("fact-x").digest == pb.digest


def _d(name: str) -> str:
    return sha256_json({"digest": name})


def test_state_epoch_is_monotonic_signed_and_replay_resistant(tmp_path):
    signer = Ed25519ReceiptSigner.generate(key_id="state-epoch")
    reg = StateEpochRegistry(tmp_path / "epochs", verifier=signer.verifier())

    e0 = StateEpoch.create(
        epoch=0,
        predecessor_digest=None,
        foundation_model_digest=_d("model"),
        tokenizer_digest=_d("tokenizer"),
        runtime_manifest_digest=_d("runtime-0"),
        belief_snapshot_digest=_d("beliefs-0"),
        skill_snapshot_digest=_d("skills-0"),
        memory_policy_digest=_d("memory-policy"),
        retrieval_policy_digest=_d("retrieval-policy"),
        adapter_set_digest=_d("adapters"),
        promotion_decision_digest=_d("promotion-0"),
    )
    reg.prepare(e0)
    body0 = reg.transition_body(
        transition_id="t0", nonce="n0", from_digest=None, to_digest=e0.digest,
        from_epoch=-1, to_epoch=0, previous_transition_digest=None, reason="genesis",
    )
    state0 = reg.activate(e0.digest, signer.issue(body0))
    assert state0["epoch"] == 0

    e1 = StateEpoch.create(
        epoch=1,
        predecessor_digest=e0.digest,
        foundation_model_digest=_d("model"),
        tokenizer_digest=_d("tokenizer"),
        runtime_manifest_digest=_d("runtime-1"),
        belief_snapshot_digest=_d("beliefs-1"),
        skill_snapshot_digest=_d("skills-1"),
        memory_policy_digest=_d("memory-policy"),
        retrieval_policy_digest=_d("retrieval-policy"),
        adapter_set_digest=_d("adapters"),
        promotion_decision_digest=_d("promotion-1"),
    )
    reg.prepare(e1)
    body1 = reg.transition_body(
        transition_id="t1", nonce="n1", from_digest=e0.digest, to_digest=e1.digest,
        from_epoch=0, to_epoch=1, previous_transition_digest=state0["transition_digest"], reason="qualified promotion",
    )
    state1 = reg.activate(e1.digest, signer.issue(body1))
    assert state1["epoch"] == 1
    assert reg.active().digest == e1.digest
    assert reg.verify()["transitions"] == 2

    # Old signed receipts cannot be replayed after the active predecessor changes.
    with pytest.raises(RuntimeError, match="predecessor mismatch"):
        reg.activate(e0.digest, signer.issue(body0))
