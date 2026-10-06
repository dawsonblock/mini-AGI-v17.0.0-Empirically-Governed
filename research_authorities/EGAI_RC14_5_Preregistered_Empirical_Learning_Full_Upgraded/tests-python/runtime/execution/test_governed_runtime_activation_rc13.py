from __future__ import annotations

import secrets
import pytest

from kvcontinual.execution.activation import RuntimeActivationRegistry, issue_runtime_transition
from kvcontinual.execution.authority import Ed25519ReceiptSigner
from kvcontinual.execution.governed_manifest import GovernedRuntimeManifest


def d(ch: str) -> str:
    return "sha256:" + ch * 64


def manifest(*, runtime_id: str, generation: int, seq: int, decision: str, adapter: str = "a") -> GovernedRuntimeManifest:
    return GovernedRuntimeManifest.create(
        runtime_id=runtime_id,
        generation=generation,
        transition_sequence=seq,
        foundation_model_digest=d("1"),
        tokenizer_digest=d("2"),
        execution_engine_digest=d("3"),
        execution_config_digest=d("4"),
        kvmem_implementation_digest=d("5"),
        gdn_implementation_digest=d("6"),
        attention_implementation_digest=d("7"),
        adapter_digests=(d(adapter),),
        skill_digests=(),
        memory_policy_digest=d("8"),
        candidate_digest=d("9"),
        build_manifest_digest=d("b"),
        evaluation_bundle_digest=d("c"),
        qualification_record_digest=d("d"),
        promotion_decision_digest=decision,
        platform_qualification_digest=d("e"),
    )


def test_exact_manifest_activation_and_replay_rejection(tmp_path):
    signer = Ed25519ReceiptSigner.generate(key_id="rc11.8-promotion")
    reg = RuntimeActivationRegistry(tmp_path, verifier=signer.verifier())
    m = manifest(runtime_id="r1", generation=1, seq=1, decision=d("f"))
    reg.manifests.put(m)
    receipt = issue_runtime_transition(
        signer,
        transition_id="t1",
        kind="promotion",
        nonce=secrets.token_hex(16),
        from_runtime_digest=None,
        to_runtime_digest=m.digest,
        from_generation=0,
        to_generation=1,
        transition_sequence=1,
        promotion_decision_digest=m.promotion_decision_digest,
        previous_transition_digest=None,
        reason="qualified promotion",
    )
    out = reg.activate(m.digest, receipt)
    assert out["runtime_manifest_digest"] == m.digest
    assert reg.state()["runtime_digest"] == m.digest
    with pytest.raises(RuntimeError):
        reg.activate(m.digest, receipt)


def test_artifact_substitution_is_rejected(tmp_path):
    signer = Ed25519ReceiptSigner.generate(key_id="rc11.8-promotion")
    reg = RuntimeActivationRegistry(tmp_path, verifier=signer.verifier())
    approved = manifest(runtime_id="approved", generation=1, seq=1, decision=d("f"), adapter="a")
    substituted = manifest(runtime_id="substituted", generation=1, seq=1, decision=d("f"), adapter="0")
    reg.manifests.put(approved)
    reg.manifests.put(substituted)
    receipt = issue_runtime_transition(
        signer,
        transition_id="t1",
        kind="promotion",
        nonce=secrets.token_hex(16),
        from_runtime_digest=None,
        to_runtime_digest=approved.digest,
        from_generation=0,
        to_generation=1,
        transition_sequence=1,
        promotion_decision_digest=approved.promotion_decision_digest,
        previous_transition_digest=None,
        reason="qualified promotion",
    )
    with pytest.raises(RuntimeError, match="target runtime manifest"):
        reg.activate(substituted.digest, receipt)


def test_signed_rollback_is_monotonic_and_nonce_bound(tmp_path):
    signer = Ed25519ReceiptSigner.generate(key_id="rc11.8-promotion")
    reg = RuntimeActivationRegistry(tmp_path, verifier=signer.verifier())
    r1 = manifest(runtime_id="r1", generation=1, seq=1, decision=d("f"))
    reg.manifests.put(r1)
    p = issue_runtime_transition(
        signer, transition_id="p1", kind="promotion", nonce="n-p1",
        from_runtime_digest=None, to_runtime_digest=r1.digest, from_generation=0, to_generation=1,
        transition_sequence=1, promotion_decision_digest=r1.promotion_decision_digest,
        previous_transition_digest=None, reason="promote")
    reg.activate(r1.digest, p)
    prev = reg.state()["transition_digest"]
    r0 = manifest(runtime_id="r0", generation=0, seq=2, decision=d("a"))
    reg.manifests.put(r0)
    rb = issue_runtime_transition(
        signer, transition_id="rb1", kind="rollback", nonce="n-rb1",
        from_runtime_digest=r1.digest, to_runtime_digest=r0.digest, from_generation=1, to_generation=0,
        transition_sequence=2, promotion_decision_digest=r0.promotion_decision_digest,
        previous_transition_digest=prev, reason="regression")
    out = reg.activate(r0.digest, rb)
    assert out["sequence"] == 2
    assert reg.state()["runtime_digest"] == r0.digest
    with pytest.raises(RuntimeError):
        reg.activate(r0.digest, rb)
