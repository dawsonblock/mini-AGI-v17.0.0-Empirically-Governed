from __future__ import annotations

import json, os, sqlite3, subprocess, sys
import pytest

from kvcontinual.execution.authority import Ed25519ReceiptSigner
from minagi.egai.canonical import sha256_json
from minagi.rc14 import (
    AdaptiveReplayScheduler, AuthorityArtifactStore, AuthorityState, AuthorityStateRegistry,
    BuildManifestRC14, CandidateManifestRC14, CandidateState, ContinualMetrics, DreamCandidate, DreamPolicyResearcher,
    DurableFreshTaskAuthority, EvidenceStrength, EvaluationBundleRC14, FalsificationCase, FalsificationKind,
    FalsificationOutcome, FalsificationPlan, FalsificationRun, GovernanceCoordinates, GovernancePolicyRC14,
    LearningMechanism, LearningProposalRC14, ModelTimeClock, PermanenceLevel, PreregisteredPlanStore,
    PromotionAuthorizationRC14, PromotionDecisionRC14, QualificationEvidenceRC14, EvidenceAttestationRC14,
    QualificationEngineRC14, QualificationRecordRC14, StateEpochRegistryRC14,
    TransactionalCandidateStateStore, backward_transfer, forgetting, forward_transfer, interference_matrix,
)
from minagi.rc14.models import EpochState


def d(name: str) -> str: return sha256_json({"d": name})

def proposal(level=PermanenceLevel.L4_REUSABLE_SKILL, evidence=EvidenceStrength.E3_REPLICATED):
    return LearningProposalRC14(target="skill:normalize", mechanism=LearningMechanism.SKILL,
        coordinates=GovernanceCoordinates(level, evidence), evidence_digests=(d("e1"), d("e2")), rationale_digest=d("rationale"),
        proposer_id="dream-researcher", production_identity_digest=d("runtime"), expected_gain=0.2, expected_transfer=0.1)


def authority(tmp_path, policy, key_ids):
    root_signer = Ed25519ReceiptSigner.generate(key_id="authority-root")
    reg = AuthorityStateRegistry(tmp_path / "authority", verifier=root_signer.verifier())
    state = AuthorityState(1, policy.policy_generation, policy.digest, tuple(key_ids))
    reg.activate(state, receipt=root_signer.issue(reg.body(state)))
    return reg, state, root_signer


def lifecycle_artifacts(store: AuthorityArtifactStore, policy: GovernancePolicyRC14, p: LearningProposalRC14, authority_state_digest: str):
    cm = CandidateManifestRC14(p.digest, d("candidate-bytes"), int(p.coordinates.permanence), policy.digest); cd = store.put(cm)
    bm = BuildManifestRC14(cd, d("build-env"), d("build-output")); bd = store.put(bm)
    ev = EvaluationBundleRC14(cd, bd, d("plan"), d("run"), d("eval-env")); ed = store.put(ev)
    qe = QualificationEvidenceRC14(cd, ed, d("plan"), d("run"), 1.0, True, True, True, True, False, False,
        "independent-evaluator", d("eval-env"), d("task-set"), independently_verified=True, replicated=True); qed = store.put(qe)
    q = QualificationRecordRC14(p.digest, cd, ed, policy.digest, True, qed, independently_verified=True, replicated=True,
        retention_passed=True, negative_controls_passed=True, security_passed=True); qd = store.put(q)
    dec = PromotionDecisionRC14(cd, qd, policy.digest, True); dd = store.put(dec)
    auth = PromotionAuthorizationRC14(cd, qd, dd, policy.digest, authority_state_digest); ad = store.put(auth)
    return cm, cd, bd, ed, q, qd, dd, ad


def sign_candidate(store, signer, *, candidate, state, actor, authority_state, stage="", qualification="", authorization="", reason=""):
    snap = store.snapshot(candidate)
    body = store.transition_body(candidate_digest=candidate, previous_state=snap["state"], new_state=state.value,
        previous_event_digest=snap["last_event_digest"], actor=actor, authority_generation=authority_state.generation,
        policy_generation=authority_state.policy_generation, stage_artifact_digest=stage, qualification_digest=qualification,
        authorization_digest=authorization, authority_state_digest=authority_state.digest, reason=reason,
        transition_id="ct-"+state.value.lower()+"-"+os.urandom(3).hex(), nonce=os.urandom(8).hex())
    return signer.issue(body)


def test_policy_uses_verified_qualification_not_proposal_claim():
    policy = GovernancePolicyRC14(); p = proposal()
    ok, reasons = policy.evaluate(p)
    assert not ok and any("verified qualification" in x for x in reasons)
    q = QualificationRecordRC14(p.digest, d("candidate"), d("eval"), policy.digest, True, d("qevidence"), independently_verified=True,
        replicated=True, retention_passed=True, negative_controls_passed=True, security_passed=True)
    assert policy.evaluate_verified(p, q)[0]
    fake_e4 = proposal(PermanenceLevel.L6_ISOLATED_NEURAL_MEMORY, EvidenceStrength.E4_FRESH_OOD_VALIDATED)
    q2 = QualificationRecordRC14(fake_e4.digest, d("candidate2"), d("eval2"), policy.digest, True, d("qevidence2"), independently_verified=True,
        replicated=True, retention_passed=True, negative_controls_passed=True, security_passed=True)
    ok, reasons = policy.evaluate_verified(fake_e4, q2)
    assert not ok and any("fresh" in r.lower() or "below required" in r.lower() for r in reasons)


def test_candidate_lifecycle_is_artifact_bound_signed_and_replay_resistant(tmp_path):
    policy = GovernancePolicyRC14()
    signers = {s.value: Ed25519ReceiptSigner.generate(key_id="role-"+s.value.lower()) for s in (
        CandidateState.QUALIFIED, CandidateState.AUTHORIZED, CandidateState.EPOCH_PREPARED, CandidateState.COMMITTED,
        CandidateState.WITNESSED, CandidateState.ATTESTED, CandidateState.SERVABLE, CandidateState.ROLLED_BACK, CandidateState.REVOKED, CandidateState.RETIRED)}
    authreg, astate, _ = authority(tmp_path, policy, [s.key_id for s in signers.values()])
    artifacts = AuthorityArtifactStore(tmp_path / "artifacts"); p = proposal(); _, candidate, build, evaluation, _, qual, decision, auth = lifecycle_artifacts(artifacts, policy, p, astate.digest)
    store = TransactionalCandidateStateStore(tmp_path / "candidate", verifiers={k:s.verifier() for k,s in signers.items()}, artifacts=artifacts, authority_registry=authreg)
    store.transition(candidate_digest=candidate, new_state=CandidateState.REGISTERED, actor="research", authority_generation=1, policy_generation=1, stage_artifact_digest=candidate)
    store.transition(candidate_digest=candidate, new_state=CandidateState.BUILT, actor="builder", authority_generation=1, policy_generation=1, stage_artifact_digest=build)
    store.transition(candidate_digest=candidate, new_state=CandidateState.EVALUATED, actor="evaluator", authority_generation=1, policy_generation=1, stage_artifact_digest=evaluation)
    with pytest.raises(PermissionError):
        store.transition(candidate_digest=candidate, new_state=CandidateState.QUALIFIED, actor="qualifier", authority_generation=1, policy_generation=1)
    receipt = sign_candidate(store, signers[CandidateState.QUALIFIED.value], candidate=candidate, state=CandidateState.QUALIFIED, actor="qualifier", authority_state=astate, stage=qual, qualification=qual)
    store.transition(candidate_digest=candidate, new_state=CandidateState.QUALIFIED, actor="qualifier", authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, stage_artifact_digest=qual, qualification_digest=qual, receipt=receipt)
    receipt = sign_candidate(store, signers[CandidateState.AUTHORIZED.value], candidate=candidate, state=CandidateState.AUTHORIZED, actor="promotion", authority_state=astate, stage=auth, qualification=qual, authorization=auth, reason="qualified")
    out = store.transition(candidate_digest=candidate, new_state=CandidateState.AUTHORIZED, actor="promotion", authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, stage_artifact_digest=auth, qualification_digest=qual, authorization_digest=auth, receipt=receipt, reason="qualified")
    assert out["state"] == CandidateState.AUTHORIZED.value and store.verify()["events"] == 5
    with pytest.raises(PermissionError):
        store.transition(candidate_digest=candidate, new_state=CandidateState.EPOCH_PREPARED, actor="state", authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, authorization_digest=auth, receipt=receipt)


def test_candidate_head_deletion_is_detected(tmp_path):
    policy=GovernancePolicyRC14(); artifacts=AuthorityArtifactStore(tmp_path/"a"); p=proposal(); cm=CandidateManifestRC14(p.digest,d("body"),4,policy.digest); cd=artifacts.put(cm)
    store=TransactionalCandidateStateStore(tmp_path/"c", artifacts=artifacts)
    store.transition(candidate_digest=cd,new_state=CandidateState.REGISTERED,actor="r",authority_generation=1,policy_generation=1,stage_artifact_digest=cd)
    with sqlite3.connect(store.db_path) as c: c.execute("DELETE FROM candidate_state WHERE candidate_digest=?",(cd,)); c.commit()
    with pytest.raises(RuntimeError, match="bijection"): store.verify()


def test_candidate_plain_transition_is_process_serialized(tmp_path):
    root=tmp_path/"candidate-race"; artifacts=AuthorityArtifactStore(root/"authority_artifacts"); policy=GovernancePolicyRC14(); p=proposal()
    cm=CandidateManifestRC14(p.digest,d("race-body"),4,policy.digest); candidate=artifacts.put(cm); build=artifacts.put(BuildManifestRC14(candidate,d("env"),d("out")))
    store=TransactionalCandidateStateStore(root, artifacts=artifacts)
    store.transition(candidate_digest=candidate,new_state=CandidateState.REGISTERED,actor="research",authority_generation=1,policy_generation=1,stage_artifact_digest=candidate)
    repo=os.path.dirname(os.path.dirname(os.path.dirname(__file__))); helper=os.path.join(repo,"tools","rc14_candidate_racer.py"); env=dict(os.environ); env["PYTHONPATH"]=os.path.join(repo,"src-python")+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    procs=[subprocess.Popen([sys.executable,helper,str(root),candidate,build,f"builder-{i}"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env) for i in range(2)]
    results=[]
    for p1 in procs:
        out,err=p1.communicate(timeout=30); assert p1.returncode==0,err; results.append(json.loads(out))
    assert sum(bool(r["ok"]) for r in results)==1 and TransactionalCandidateStateStore(root).snapshot(candidate)["state"]==CandidateState.BUILT.value


def epoch_setup(tmp_path):
    policy=GovernancePolicyRC14(); states=[EpochState.AUTHORIZED,EpochState.LOCALLY_COMMITTED,EpochState.EXTERNALLY_WITNESSED,EpochState.ATTESTED,EpochState.SERVABLE,EpochState.RETIRED]
    signers={s.value:Ed25519ReceiptSigner.generate(key_id="epoch-"+s.value.lower()) for s in states}
    authreg,astate,_=authority(tmp_path,policy,[s.key_id for s in signers.values()]); artifacts=AuthorityArtifactStore(tmp_path/"artifacts")
    p=proposal(); _, candidate, build, evaluation, q, qd, dd, ad=lifecycle_artifacts(artifacts,policy,p,astate.digest)
    comps={"foundation_model_digest":d("model"),"tokenizer_digest":d("tokenizer"),"evidence_root":d("evidence-root"),"belief_snapshot_digest":d("beliefs"),"episodic_memory_root":d("episodes"),"semantic_memory_root":d("semantic"),"skill_graph_root":d("skills"),"procedure_root":d("procedures"),"retrieval_policy_digest":d("retrieval-policy"),"retrieval_index_digest":d("retrieval-index"),"adapter_set_digest":d("adapters"),"isolated_neural_memory_root":d("isolated-neural"),"plasticity_policy_digest":d("plasticity"),"governance_policy_digest":policy.digest,"execution_manifest_digest":d("runtime-manifest"),"runtime_config_digest":d("runtime-config"),"qualification_bundle_digest":qd,"promotion_decision_digest":dd,"promotion_authorization_digest":ad,"source_tree_digest":d("source"),"dependency_lock_digest":d("deps"),"build_provenance_digest":d("provenance"),"target_platform_policy_digest":d("platform"),"runtime_attestation_policy_digest":d("attestation-policy")}
    reg=StateEpochRegistryRC14(tmp_path/"epochs",verifiers={k:v.verifier() for k,v in signers.items()},artifacts=artifacts,authority_registry=authreg)
    return policy,signers,authreg,astate,artifacts,reg,comps


def sign_epoch(reg, signer, astate, digest, from_state, to_state, *, artifact="", reason=""):
    ctl=reg.snapshot(); body=reg.transition_body(epoch_digest=digest,from_state=from_state,to_state=to_state,previous_transition_digest=ctl["transition_digest"],authority_generation=astate.generation,policy_generation=astate.policy_generation,authority_state_digest=astate.digest,artifact_digest=artifact,previous_serving_digest=ctl["serving_epoch_digest"] if to_state in {EpochState.SERVABLE.value,EpochState.RETIRED.value} else None,reason=reason,transition_id="et-"+os.urandom(5).hex(),nonce=os.urandom(8).hex()); return signer.issue(body)


def advance_epoch(reg,signers,astate,e):
    ad=e.promotion_authorization_digest
    r=sign_epoch(reg,signers[EpochState.AUTHORIZED.value],astate,e.digest,EpochState.PREPARED.value,EpochState.AUTHORIZED.value,artifact=ad,reason="promote"); reg.authorize(e.digest,authorization_digest=ad,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="promote")
    r=sign_epoch(reg,signers[EpochState.LOCALLY_COMMITTED.value],astate,e.digest,EpochState.AUTHORIZED.value,EpochState.LOCALLY_COMMITTED.value,reason="commit"); reg.local_commit(e.digest,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="commit")
    w=d("w-"+str(e.epoch)); r=sign_epoch(reg,signers[EpochState.EXTERNALLY_WITNESSED.value],astate,e.digest,EpochState.LOCALLY_COMMITTED.value,EpochState.EXTERNALLY_WITNESSED.value,artifact=w,reason="witness"); reg.witness(e.digest,witness_digest=w,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="witness")
    t=d("t-"+str(e.epoch)); r=sign_epoch(reg,signers[EpochState.ATTESTED.value],astate,e.digest,EpochState.EXTERNALLY_WITNESSED.value,EpochState.ATTESTED.value,artifact=t,reason="attest"); reg.attest(e.digest,attestation_digest=t,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="attest")
    r=sign_epoch(reg,signers[EpochState.SERVABLE.value],astate,e.digest,EpochState.ATTESTED.value,EpochState.SERVABLE.value,reason="serve"); reg.make_servable(e.digest,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="serve")


def test_rich_state_epoch_lifecycle_pinning_and_signed_retirement(tmp_path):
    policy,signers,authreg,astate,artifacts,reg,comps=epoch_setup(tmp_path); e0=reg.prepare(comps); advance_epoch(reg,signers,astate,e0)
    with reg.pin("request-1") as ctx:
        assert ctx.epoch_digest==e0.digest and reg.validate_context(ctx).digest==e0.digest
    e1=reg.prepare_rollback(e0.digest,overrides={"runtime_config_digest":d("runtime-config-2")}); advance_epoch(reg,signers,astate,e1)
    assert reg.get(e0.digest)[1] is EpochState.SERVABLE
    r=sign_epoch(reg,signers[EpochState.RETIRED.value],astate,e0.digest,EpochState.SERVABLE.value,EpochState.RETIRED.value,reason="superseded"); reg.retire(e0.digest,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="superseded")
    status=reg.verify(); assert status["epochs"]==2 and status["transitions"]==11 and status["serving_epoch_digest"]==e1.digest


def test_epoch_authorization_digest_mismatch_and_metadata_tamper_are_rejected(tmp_path):
    _,signers,_,astate,_,reg,comps=epoch_setup(tmp_path); e=reg.prepare(comps)
    wrong=d("wrong-auth"); r=sign_epoch(reg,signers[EpochState.AUTHORIZED.value],astate,e.digest,EpochState.PREPARED.value,EpochState.AUTHORIZED.value,artifact=wrong,reason="bad")
    with pytest.raises(PermissionError,match="promotion_authorization"): reg.authorize(e.digest,authorization_digest=wrong,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="bad")
    r=sign_epoch(reg,signers[EpochState.AUTHORIZED.value],astate,e.digest,EpochState.PREPARED.value,EpochState.AUTHORIZED.value,artifact=e.promotion_authorization_digest,reason="ok"); reg.authorize(e.digest,authorization_digest=e.promotion_authorization_digest,receipt=r,authority_generation=1,policy_generation=1,authority_state_digest=astate.digest,reason="ok")
    with sqlite3.connect(reg.db_path) as c: c.execute("UPDATE epochs SET authorization_digest=? WHERE epoch_digest=?",(d("tampered"),e.digest)); c.commit()
    with pytest.raises(RuntimeError,match="authorization_digest"): reg.verify()


def test_fresh_task_is_one_shot_encrypted_at_rest_and_commitment_bound(tmp_path):
    auth=DurableFreshTaskAuthority(tmp_path/"fresh"); secret="DO_NOT_STORE_PLAINTEXT_9347"; commitment=auth.seal({"question":secret},generation=7)
    raw=auth.path.read_bytes(); assert secret.encode() not in raw
    with sqlite3.connect(auth.path) as c: cols={r[1] for r in c.execute("PRAGMA table_info(tasks)")}; assert "task_json" not in cols and "salt" not in cols
    lease=auth.lease(task_id=commitment.task_id,consumer_id="evaluator"); assert auth.consume(lease)["question"]==secret
    with pytest.raises(PermissionError): auth.consume(lease)
    assert auth.reveal(commitment.task_id)["commitment_valid"]


def test_preregistered_falsification_is_fail_closed_even_if_plan_requests_zero_threshold(tmp_path):
    cases=tuple(FalsificationCase(name,kind,d(name+"-payload"),d(name+"-expected")) for name,kind in (("n",FalsificationKind.NEGATIVE_CONTROL),("r",FalsificationKind.RETENTION),("s",FalsificationKind.SECURITY)))
    plan=FalsificationPlan(d("candidate-f"),GovernancePolicyRC14().digest,cases,"independent-planner",min_pass_rate=0.0); store=PreregisteredPlanStore(tmp_path/"plans"); store.seal(plan)
    outcomes=tuple(FalsificationOutcome(c.case_id,c.digest,c.kind is FalsificationKind.SECURITY,1.0 if c.kind is FalsificationKind.SECURITY else 0.0,d(c.case_id+"-result")) for c in cases)
    run=FalsificationRun(plan.digest,plan.candidate_digest,outcomes,"evaluator",d("env"),d("task-set")); result=run.validate_against(plan)
    assert not result["passed"] and result["effective_min_pass_rate"]==1.0


def test_authority_state_rejects_old_generation_after_rotation(tmp_path):
    policy=GovernancePolicyRC14(); transition=Ed25519ReceiptSigner.generate(key_id="transition-v1"); root=Ed25519ReceiptSigner.generate(key_id="root"); reg=AuthorityStateRegistry(tmp_path/"auth",verifier=root.verifier())
    s1=AuthorityState(1,1,policy.digest,(transition.key_id,)); reg.activate(s1,receipt=root.issue(reg.body(s1)))
    s2=AuthorityState(2,1,policy.digest,("transition-v2",),revoked_key_ids=(transition.key_id,),previous_authority_state_digest=s1.digest); reg.activate(s2,receipt=root.issue(reg.body(s2)))
    with pytest.raises(PermissionError,match="current authority state"): reg.assert_current(authority_state_digest=s1.digest,authority_generation=1,policy_generation=1,receipt=transition.issue({"x":1}))
    assert reg.verify()["generation"]==2


def test_dream_is_proposal_only_and_replay_metrics_are_explicit():
    dream=DreamPolicyResearcher(); a=DreamCandidate("a",d("p"),1.0,0.1,0.8,0.1,0.2,0.1,(d("w1"),)); b=DreamCandidate("b",d("p"),0.8,0.7,0.1,0.1,0.0,0.8,(d("w2"),))
    assert dream.propose((a,b)).candidate_id=="b" and not dream.can_qualify and not dream.can_promote and not dream.can_activate and not dream.can_commit
    clock=ModelTimeClock(); clock.advance(0.25); decision=AdaptiveReplayScheduler(model_time_interval=1.0,min_priority=1.0).decide(model_time=clock.value,estimated_forgetting_risk=0.8,memory_importance=0.4,uncertainty=0.2,age_model_time=0.5); assert decision.should_replay
    assert forgetting((0.5,0.8,0.7),0.6)==pytest.approx(0.2); assert forward_transfer(0.8,0.5)==pytest.approx(0.3); assert backward_transfer(0.75,0.7)==pytest.approx(0.05); assert interference_matrix({"a":0.8},{"a":0.6})["a"]==pytest.approx(-0.2)
    ContinualMetrics(0.2,0.1,0.2,0.3,0.0,0.9,0,0,1.0,2.0,0.1,0.8).validate()


def test_governed_rc14_system_keeps_legacy_and_rc14_registries_separate(tmp_path):
    from kvcontinual.execution.recurrent.interfaces import BackendCapabilities
    from minagi.rc14 import GovernedRC14System
    class Backend:
        def capabilities(self): return BackendCapabilities(hypic_seam8=True, causal_conv_seam_repair=True, full_attention_relocation=True)
        def exact_selected_replay(self, ids): return ("exact", ids)
        def materialize(self, *args): raise AssertionError("unexpected acceleration")
    promotion = Ed25519ReceiptSigner.generate(key_id="promotion")
    authority_root = Ed25519ReceiptSigner.generate(key_id="authority-root")
    system = GovernedRC14System(tmp_path / "system", Backend(), research_verifier=None, promotion_signer=promotion,
        rc14_epoch_verifiers={}, rc14_candidate_verifiers={}, rc14_authority_verifier=authority_root.verifier())
    assert system.state_epochs is system.legacy_state_epochs
    assert system.rc14_state_epochs is not system.state_epochs
    result = system.verify_control_plane()
    assert "legacy_state_epochs" in result and "rc14_state_epochs" in result and "rc14_authority" in result and "rc14_falsification" in result
    deep = system.verify_rc14_deep()
    assert deep["rc14_cross_plane"]["status"] == "verified"
    system.close()


def test_governed_rc14_system_preserves_legacy_registry_contract(tmp_path):
    from kvcontinual.execution.recurrent.interfaces import BackendCapabilities
    from minagi.rc14 import GovernedRC14System

    class Backend:
        def capabilities(self):
            return BackendCapabilities(hypic_seam8=True, causal_conv_seam_repair=True, full_attention_relocation=True)
        def exact_selected_replay(self, ids):
            return ("exact", ids)
        def materialize(self, *args):
            raise AssertionError("unqualified acceleration reached")

    promotion = Ed25519ReceiptSigner.generate(key_id="promotion")
    authority_root = Ed25519ReceiptSigner.generate(key_id="authority-root")
    system = GovernedRC14System(
        tmp_path / "runtime",
        Backend(),
        research_verifier=None,
        promotion_signer=promotion,
        rc14_epoch_verifiers={},
        rc14_candidate_verifiers={},
        rc14_authority_verifier=authority_root.verifier(),
    )
    try:
        # Regression guard: RC14 must not overwrite the inherited RC13 registry.
        assert system.state_epochs is system.legacy_state_epochs
        assert system.rc14_state_epochs is not system.state_epochs
        status = system.verify_control_plane()
        assert "legacy_state_epochs" in status
        assert "rc14_state_epochs" in status
        assert status["rc14_candidate_states"]["events"] == 0
    finally:
        system.close()


def test_fresh_task_service_client_has_no_key_or_database_path(tmp_path):
    import threading, time
    from minagi.rc14 import FreshTaskAuthorityClient, FreshTaskAuthorityAdminClient, FreshTaskAuthorityServer

    authority = DurableFreshTaskAuthority(tmp_path / "authority-private")
    socket_path = tmp_path / "run" / "fresh-task.sock"
    server = FreshTaskAuthorityServer(socket_path, authority, evaluator_token="eval-token-abcdefghijklmnopqrstuvwxyz", admin_token="admin-token-abcdefghijklmnopqrstuvwxyz")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    for _ in range(100):
        if socket_path.exists():
            break
        time.sleep(0.01)
    client = FreshTaskAuthorityClient(socket_path, token="eval-token-abcdefghijklmnopqrstuvwxyz")
    admin = FreshTaskAuthorityAdminClient(socket_path, token="admin-token-abcdefghijklmnopqrstuvwxyz")
    boundary = client.storage_boundary()
    assert boundary["service_isolation_supported"] and boundary["role_scoped_capabilities"]
    assert not boundary["client_has_key_material"] and not boundary["client_has_database_path"]
    assert "key_path" not in boundary and "database" not in boundary
    c = admin.seal({"secret": "hidden-over-service"}, generation=3)
    with pytest.raises(PermissionError): client.reveal(c.task_id)
    lease = client.lease(task_id=c.task_id, consumer_id="independent-evaluator")
    assert client.consume(lease)["secret"] == "hidden-over-service"
    with pytest.raises(PermissionError): client.consume(lease)
    assert admin.reveal(c.task_id)["commitment_valid"]
    with pytest.raises(PermissionError):
        FreshTaskAuthorityClient(socket_path, token="wrong-token-abcdefghijklmnopqrstuvwxyz").storage_boundary()
    server.stop(); thread.join(timeout=3)
    assert not thread.is_alive()


def test_execution_context_guard_fails_closed_and_binds_exact_epoch():
    from minagi.rc14 import ExecutionContext, ExecutionContextGuard
    guard = ExecutionContextGuard()
    with pytest.raises(PermissionError, match="pinned ExecutionContext"):
        guard.require()
    ctx = ExecutionContext("req-1", "lease-1", d("epoch-1"), 7, 10, 20)
    with guard.bind(ctx):
        assert guard.require().request_id == "req-1"
        assert guard.source_epoch_digest() == d("epoch-1")
        with pytest.raises(PermissionError, match="epoch mismatch"):
            guard.require(epoch_digest=d("epoch-2"))
    assert guard.current() is None


def test_state_epoch_rejects_cross_candidate_promotion_chain(tmp_path):
    policy, signers, authreg, astate, artifacts, reg, comps = epoch_setup(tmp_path)
    q = artifacts.get(comps["qualification_bundle_digest"], expected_kind="qualification_record")
    dec = PromotionDecisionRC14(d("different-candidate"), q.digest, policy.digest, True)
    dd = artifacts.put(dec)
    auth = PromotionAuthorizationRC14(d("different-candidate"), q.digest, dd, policy.digest, astate.digest)
    ad = artifacts.put(auth)
    bad = dict(comps, promotion_decision_digest=dd, promotion_authorization_digest=ad)
    with pytest.raises(PermissionError, match="candidate mismatch"):
        reg.prepare(bad)


def test_fresh_task_authority_runs_as_separate_process(tmp_path):
    import time
    from minagi.rc14 import FreshTaskAuthorityClient, FreshTaskAuthorityAdminClient
    repo=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    socket_path=tmp_path/"service.sock"; private_root=tmp_path/"private-authority"; key_path=tmp_path/"secrets"/"fresh.key"; key_path.parent.mkdir()
    eval_token_path=tmp_path/"secrets"/"eval.cap"; admin_token_path=tmp_path/"secrets"/"admin.cap"
    eval_token_path.write_text("eval-process-token-abcdefghijklmnopqrstuvwxyz012345\n"); admin_token_path.write_text("admin-process-token-abcdefghijklmnopqrstuvwxyz012345\n")
    os.chmod(eval_token_path,0o600); os.chmod(admin_token_path,0o600)
    env=dict(os.environ); env["PYTHONPATH"]=os.path.join(repo,"src-python")+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc=subprocess.Popen([sys.executable,"-m","minagi.rc14.fresh_task_daemon","--root",str(private_root),"--socket",str(socket_path),"--key-path",str(key_path),"--evaluator-token-file",str(eval_token_path),"--admin-token-file",str(admin_token_path)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(200):
            if socket_path.exists(): break
            if proc.poll() is not None:
                out,err=proc.communicate(); pytest.fail(f"fresh-task daemon exited early: {out} {err}")
            time.sleep(0.01)
        client=FreshTaskAuthorityClient(socket_path, token=eval_token_path.read_text().strip())
        admin=FreshTaskAuthorityAdminClient(socket_path, token=admin_token_path.read_text().strip())
        boundary=client.storage_boundary(); assert boundary["service_isolation_supported"] and boundary["role_scoped_capabilities"] and not boundary["client_has_key_material"]
        commitment=admin.seal({"q":"process-secret"},generation=9)
        with pytest.raises(PermissionError): client.reveal(commitment.task_id)
        lease=client.lease(task_id=commitment.task_id,consumer_id="eval-process")
        assert client.consume(lease)["q"]=="process-secret"
        assert admin.reveal(commitment.task_id)["commitment_valid"]
        assert key_path.exists() and len(key_path.read_bytes())==32
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)


def test_qualification_engine_derives_flags_from_recorded_run(tmp_path):
    policy=GovernancePolicyRC14(); artifacts=AuthorityArtifactStore(tmp_path/"artifacts"); plans=PreregisteredPlanStore(tmp_path/"falsification")
    p=proposal(PermanenceLevel.L4_REUSABLE_SKILL, EvidenceStrength.E0_UNVERIFIED)
    cm=CandidateManifestRC14(p.digest,d("candidate-binary"),int(p.coordinates.permanence),policy.digest); cd=artifacts.put(cm)
    bm=BuildManifestRC14(cd,d("build-env-q"),d("build-out-q")); bd=artifacts.put(bm)
    cases=tuple(FalsificationCase(name,kind,d(name+"-payload-q"),d(name+"-expect-q")) for name,kind in (("neg",FalsificationKind.NEGATIVE_CONTROL),("ret",FalsificationKind.RETENTION),("sec",FalsificationKind.SECURITY),("ood",FalsificationKind.OOD),("fresh",FalsificationKind.FRESH_HIDDEN)))
    plan=FalsificationPlan(cd,policy.digest,cases,"independent-planner"); plans.seal(plan)
    outcomes=tuple(FalsificationOutcome(c.case_id,c.digest,True,1.0,d(c.case_id+"-evidence-q")) for c in cases)
    run=FalsificationRun(plan.digest,cd,outcomes,"independent-evaluator",d("eval-env-q"),d("task-set-q")); plans.record_run(run)
    ev=EvaluationBundleRC14(cd,bd,plan.digest,run.digest,run.environment_digest); ed=artifacts.put(ev)
    signer1=Ed25519ReceiptSigner.generate(key_id="independent-verifier"); signer2=Ed25519ReceiptSigner.generate(key_id="replicator")
    def att(scope, signer, evidence):
        body={"schema":"egai-rc14-evidence-attestation-v1","scope":scope,"candidate_digest":cd,"evaluation_digest":ed,"evidence_digest":evidence,"issuer_id":signer.key_id}
        return EvidenceAttestationRC14(scope,cd,ed,evidence,signer.key_id,signer.issue(body))
    a1=artifacts.put(att("independent_verification",signer1,d("independent-proof")))
    a2=artifacts.put(att("replication",signer2,d("replication-proof")))
    engine=QualificationEngineRC14(artifacts,plans,policy,{"independent_verification":signer1.verifier(),"replication":signer2.verifier()})
    record=engine.build_and_require(p,candidate_digest=cd,evaluation_digest=ed,attestation_digests=(a1,a2))
    evidence=artifacts.get(record.qualification_evidence_digest,expected_kind="qualification_evidence")
    assert record.fresh_ood_validated and record.retention_passed and record.security_passed and record.replicated
    assert evidence.falsification_run_digest==run.digest and evidence.pass_rate==1.0


def test_qualification_engine_rejects_self_declared_or_unrecorded_evidence(tmp_path):
    policy=GovernancePolicyRC14(); artifacts=AuthorityArtifactStore(tmp_path/"artifacts"); plans=PreregisteredPlanStore(tmp_path/"falsification")
    p=proposal(); cm=CandidateManifestRC14(p.digest,d("candidate-u"),4,policy.digest); cd=artifacts.put(cm); bm=BuildManifestRC14(cd,d("env-u"),d("out-u")); bd=artifacts.put(bm)
    cases=tuple(FalsificationCase(name,kind,d(name+"p-u"),d(name+"e-u")) for name,kind in (("n",FalsificationKind.NEGATIVE_CONTROL),("r",FalsificationKind.RETENTION),("s",FalsificationKind.SECURITY)))
    plan=FalsificationPlan(cd,policy.digest,cases,"planner"); plans.seal(plan)
    fake_run_digest=d("not-recorded-run")
    ev=EvaluationBundleRC14(cd,bd,plan.digest,fake_run_digest,d("env-u")); ed=artifacts.put(ev)
    engine=QualificationEngineRC14(artifacts,plans,policy,{})
    with pytest.raises(KeyError): engine.build_record(p,candidate_digest=cd,evaluation_digest=ed)


def test_request_learning_requires_exact_execution_context():
    p=LearningProposalRC14(target="skill:x",mechanism=LearningMechanism.SKILL,coordinates=GovernanceCoordinates(PermanenceLevel.L4_REUSABLE_SKILL,EvidenceStrength.E0_UNVERIFIED),evidence_digests=(d("e"),),rationale_digest=d("r"),proposer_id="p",production_identity_digest=d("prod"),expected_gain=0.1,source_epoch_digest=d("epoch-x"),source_request_id="req-x")
    assert p.source_epoch_digest==d("epoch-x") and p.source_request_id=="req-x"
    with pytest.raises(ValueError,match="supplied together"):
        LearningProposalRC14(target="skill:y",mechanism=LearningMechanism.SKILL,coordinates=GovernanceCoordinates(PermanenceLevel.L4_REUSABLE_SKILL,EvidenceStrength.E0_UNVERIFIED),evidence_digests=(d("e2"),),rationale_digest=d("r2"),proposer_id="p",production_identity_digest=d("prod2"),expected_gain=0.1,source_epoch_digest=d("epoch-y"))


def test_evaluator_capability_cannot_invoke_admin_protocol_op(tmp_path):
    import threading, time
    from minagi.rc14 import FreshTaskAuthorityClient, FreshTaskAuthorityAdminClient, FreshTaskAuthorityServer
    authority=DurableFreshTaskAuthority(tmp_path/"private")
    sock=tmp_path/"fresh.sock"
    server=FreshTaskAuthorityServer(sock,authority,evaluator_token="eval-capability-abcdefghijklmnopqrstuvwxyz",admin_token="admin-capability-abcdefghijklmnopqrstuvwxyz")
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    for _ in range(100):
        if sock.exists(): break
        time.sleep(0.01)
    evaluator=FreshTaskAuthorityClient(sock,token="eval-capability-abcdefghijklmnopqrstuvwxyz")
    admin=FreshTaskAuthorityAdminClient(sock,token="admin-capability-abcdefghijklmnopqrstuvwxyz")
    commitment=admin.seal({"hidden":1},generation=1)
    with pytest.raises(PermissionError,match="admin capability"):
        evaluator._call({"op":"reveal","task_id":commitment.task_id})
    server.stop(); thread.join(timeout=3)


def test_strict_state_epoch_requires_typed_independent_witness_and_attestation(tmp_path):
    import time
    from minagi.rc14 import ExternalWitnessRC14, RuntimeAttestationRC14

    policy, signers, authreg, astate, artifacts, _legacy_reg, comps = epoch_setup(tmp_path)
    witness_signer = Ed25519ReceiptSigner.generate(key_id="external-witness-1")
    attestor_signer = Ed25519ReceiptSigner.generate(key_id="runtime-attestor-1")
    reg = StateEpochRegistryRC14(
        tmp_path / "strict-epochs",
        verifiers={k: v.verifier() for k, v in signers.items()},
        artifacts=artifacts,
        authority_registry=authreg,
        witness_verifiers={witness_signer.key_id: witness_signer.verifier()},
        runtime_attestation_verifiers={attestor_signer.key_id: attestor_signer.verifier()},
        strict_serving_artifacts=True,
    )
    epoch = reg.prepare(comps)
    ad = epoch.promotion_authorization_digest
    r = sign_epoch(reg, signers[EpochState.AUTHORIZED.value], astate, epoch.digest, EpochState.PREPARED.value, EpochState.AUTHORIZED.value, artifact=ad, reason="promote")
    reg.authorize(epoch.digest, authorization_digest=ad, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="promote")
    r = sign_epoch(reg, signers[EpochState.LOCALLY_COMMITTED.value], astate, epoch.digest, EpochState.AUTHORIZED.value, EpochState.LOCALLY_COMMITTED.value, reason="commit")
    reg.local_commit(epoch.digest, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="commit")

    with pytest.raises((PermissionError, FileNotFoundError)):
        opaque = d("opaque-witness")
        r = sign_epoch(reg, signers[EpochState.EXTERNALLY_WITNESSED.value], astate, epoch.digest, EpochState.LOCALLY_COMMITTED.value, EpochState.EXTERNALLY_WITNESSED.value, artifact=opaque, reason="bad witness")
        reg.witness(epoch.digest, witness_digest=opaque, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="bad witness")

    witness_body = {
        "schema": "egai-rc14-external-witness-v1",
        "epoch_digest": epoch.digest,
        "transition_head_digest": reg.snapshot()["transition_digest"],
        "authority_state_digest": astate.digest,
        "witness_id": witness_signer.key_id,
        "observed_ns": time.time_ns(),
    }
    witness = ExternalWitnessRC14(
        epoch.digest,
        witness_body["transition_head_digest"],
        astate.digest,
        witness_signer.key_id,
        witness_body["observed_ns"],
        witness_signer.issue(witness_body),
    )
    wd = artifacts.put(witness)
    r = sign_epoch(reg, signers[EpochState.EXTERNALLY_WITNESSED.value], astate, epoch.digest, EpochState.LOCALLY_COMMITTED.value, EpochState.EXTERNALLY_WITNESSED.value, artifact=wd, reason="witness")
    reg.witness(epoch.digest, witness_digest=wd, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="witness")

    bad_body = {
        "schema": "egai-rc14-runtime-attestation-v2",
        "epoch_digest": epoch.digest,
        "witness_digest": wd,
        "foundation_model_digest": epoch.foundation_model_digest,
        "tokenizer_digest": epoch.tokenizer_digest,
        "adapter_set_digest": epoch.adapter_set_digest,
        "isolated_neural_memory_root": epoch.isolated_neural_memory_root,
        "execution_manifest_digest": epoch.execution_manifest_digest,
        "runtime_config_digest": d("wrong-runtime-config"),
        "source_tree_digest": epoch.source_tree_digest,
        "dependency_lock_digest": epoch.dependency_lock_digest,
        "build_provenance_digest": epoch.build_provenance_digest,
        "target_platform_policy_digest": epoch.target_platform_policy_digest,
        "runtime_attestation_policy_digest": epoch.runtime_attestation_policy_digest,
        "authority_state_digest": astate.digest,
        "attestor_id": attestor_signer.key_id,
        "attested_ns": time.time_ns(),
    }
    bad = RuntimeAttestationRC14(
        epoch_digest=epoch.digest, witness_digest=wd, foundation_model_digest=epoch.foundation_model_digest,
        tokenizer_digest=epoch.tokenizer_digest, adapter_set_digest=epoch.adapter_set_digest,
        isolated_neural_memory_root=epoch.isolated_neural_memory_root, execution_manifest_digest=epoch.execution_manifest_digest,
        runtime_config_digest=bad_body["runtime_config_digest"], source_tree_digest=epoch.source_tree_digest,
        dependency_lock_digest=epoch.dependency_lock_digest, build_provenance_digest=epoch.build_provenance_digest,
        target_platform_policy_digest=epoch.target_platform_policy_digest, runtime_attestation_policy_digest=epoch.runtime_attestation_policy_digest,
        authority_state_digest=astate.digest, attestor_id=attestor_signer.key_id, attested_ns=bad_body["attested_ns"],
        receipt=attestor_signer.issue(bad_body),
    )
    bad_digest = artifacts.put(bad)
    r = sign_epoch(reg, signers[EpochState.ATTESTED.value], astate, epoch.digest, EpochState.EXTERNALLY_WITNESSED.value, EpochState.ATTESTED.value, artifact=bad_digest, reason="bad attestation")
    with pytest.raises(PermissionError, match="runtime attestation runtime_config_digest mismatch"):
        reg.attest(epoch.digest, attestation_digest=bad_digest, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="bad attestation")

    att_body = {
        "schema": "egai-rc14-runtime-attestation-v2",
        "epoch_digest": epoch.digest,
        "witness_digest": wd,
        "foundation_model_digest": epoch.foundation_model_digest,
        "tokenizer_digest": epoch.tokenizer_digest,
        "adapter_set_digest": epoch.adapter_set_digest,
        "isolated_neural_memory_root": epoch.isolated_neural_memory_root,
        "execution_manifest_digest": epoch.execution_manifest_digest,
        "runtime_config_digest": epoch.runtime_config_digest,
        "source_tree_digest": epoch.source_tree_digest,
        "dependency_lock_digest": epoch.dependency_lock_digest,
        "build_provenance_digest": epoch.build_provenance_digest,
        "target_platform_policy_digest": epoch.target_platform_policy_digest,
        "runtime_attestation_policy_digest": epoch.runtime_attestation_policy_digest,
        "authority_state_digest": astate.digest,
        "attestor_id": attestor_signer.key_id,
        "attested_ns": time.time_ns(),
    }
    att = RuntimeAttestationRC14(
        epoch_digest=epoch.digest, witness_digest=wd, foundation_model_digest=epoch.foundation_model_digest,
        tokenizer_digest=epoch.tokenizer_digest, adapter_set_digest=epoch.adapter_set_digest,
        isolated_neural_memory_root=epoch.isolated_neural_memory_root, execution_manifest_digest=epoch.execution_manifest_digest,
        runtime_config_digest=epoch.runtime_config_digest, source_tree_digest=epoch.source_tree_digest,
        dependency_lock_digest=epoch.dependency_lock_digest, build_provenance_digest=epoch.build_provenance_digest,
        target_platform_policy_digest=epoch.target_platform_policy_digest, runtime_attestation_policy_digest=epoch.runtime_attestation_policy_digest,
        authority_state_digest=astate.digest, attestor_id=attestor_signer.key_id, attested_ns=att_body["attested_ns"],
        receipt=attestor_signer.issue(att_body),
    )
    td = artifacts.put(att)
    r = sign_epoch(reg, signers[EpochState.ATTESTED.value], astate, epoch.digest, EpochState.EXTERNALLY_WITNESSED.value, EpochState.ATTESTED.value, artifact=td, reason="attest")
    reg.attest(epoch.digest, attestation_digest=td, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="attest")
    r = sign_epoch(reg, signers[EpochState.SERVABLE.value], astate, epoch.digest, EpochState.ATTESTED.value, EpochState.SERVABLE.value, reason="serve")
    reg.make_servable(epoch.digest, receipt=r, authority_generation=1, policy_generation=1, authority_state_digest=astate.digest, reason="serve")
    assert reg.verify()["serving_epoch_digest"] == epoch.digest


def test_fresh_task_secret_files_fail_closed_on_insecure_permissions(tmp_path):
    from minagi.rc14.fresh_task_daemon import _load_or_create_token
    token = tmp_path / "eval.cap"
    token.write_text("x" * 64 + "\n")
    os.chmod(token, 0o644)
    with pytest.raises(RuntimeError, match="permissions"):
        _load_or_create_token(token)

    key = tmp_path / "fresh.key"
    key.write_bytes(b"k" * 32)
    os.chmod(key, 0o644)
    with pytest.raises(RuntimeError, match="permissions"):
        DurableFreshTaskAuthority(tmp_path / "fresh-insecure", key_path=key)


def test_system_request_context_pins_entire_logical_request_and_rejects_nesting():
    from contextlib import contextmanager
    from minagi.rc14 import ExecutionContext, ExecutionContextGuard, GovernedRC14System

    ctx = ExecutionContext("REQ-whole", "LEASE-whole", d("epoch-whole"), 4, 10, 1000)

    class FakeEpochs:
        @contextmanager
        def pin(self, request_id, *, ttl_seconds=3600):
            assert request_id == "REQ-whole"
            assert ttl_seconds == 123
            yield ctx
        def validate_context(self, context):
            assert context is ctx
            return object()

    system = object.__new__(GovernedRC14System)
    system.rc14_state_epochs = FakeEpochs()
    system.execution_context_guard = ExecutionContextGuard()
    with system.request_context("REQ-whole", ttl_seconds=123) as bound:
        assert bound is ctx
        assert system.require_execution_context() is ctx
        with pytest.raises(PermissionError, match="nested"):
            with system.request_context("REQ-nested"):
                pass
    assert system.current_execution_context() is None
