from dataclasses import asdict
import json
import sqlite3

import pytest

from kvcontinual.execution.authority import Ed25519ReceiptSigner

from minagi.egai.canonical import sha256_json
from minagi.rc14 import (
    AblationQualificationCertificateRC14,
    AuthorityArtifactStore,
    ContinualExperimentEvidenceRC14,
    ContinualExperimentHarnessRC14,
    ContinualExperimentMeasurement,
    DEFAULT_ABLATION_LADDER,
    FrozenFoundationProofRC14,
    GovernancePolicyRC14, GovernanceCoordinates, EvidenceStrength, PermanenceLevel, LearningMechanism, LearningProposalRC14,
    IsolatedNeuralMemoryManifestRC14,
    IsolatedNeuralMemoryQualificationEngineRC14,
    PreregisteredContinualExperimentPlanRC14,
    PreregisteredContinualExperimentStoreRC14,
    PreregisteredPlanStore,
    QualificationEngineRC14, CandidateManifestRC14, BuildManifestRC14, EvaluationBundleRC14,
    FalsificationCase, FalsificationKind, FalsificationOutcome, FalsificationPlan, FalsificationRun, EvidenceAttestationRC14,
)


def d(x):
    return sha256_json({"x": x})


def measurement(variant, *, gain=0.12, forgetting=0.01, reproducibility=0.97):
    baseline = 0.60
    return ContinualExperimentMeasurement(
        variant=variant,
        old_task_history={"A": (0.85, 0.90), "B": (0.78, 0.82)},
        old_task_before={"A": 0.89, "B": 0.81},
        old_task_after={"A": 0.90 - forgetting, "B": 0.82 - forgetting},
        fresh_history_score=baseline + gain,
        fresh_frozen_baseline_score=baseline,
        falsification_survival=1.0,
        security_regressions=0,
        unauthorized_writes=0,
        memory_growth=5.0,
        compute_cost=2.0,
        latency_delta=0.01,
        reproducibility=reproducibility,
    )


def plan(candidate=d("candidate")):
    return PreregisteredContinualExperimentPlanRC14(
        experiment_id="exp-rc14-5",
        candidate_digest=candidate,
        base_model_digest=d("base"),
        tokenizer_digest=d("tok"),
        environment_digest=d("env"),
        task_set_digest=d("tasks"),
        hidden_task_commitment_digest=d("hidden"),
        seeds=(11, 23),
        min_fresh_task_gain=0.05,
        min_incremental_gain_over_replay=0.01,
        min_reproducibility=0.90,
    )


def fill(store, p, *, isolated_gain=0.16, replay_gain=0.12):
    harness = ContinualExperimentHarnessRC14(max_mean_forgetting=0.05, max_worst_forgetting=0.10, min_fresh_task_gain=0.0)
    for variant in p.variants:
        for seed in p.seeds:
            gain = isolated_gain if variant == "isolated_neural_memory" else replay_gain if variant == "replay" else 0.08
            result = harness.evaluate(measurement(variant, gain=gain))
            store.record_result(p.digest, variant=variant, seed=seed, result=result, evaluator_id=f"eval-{seed}", environment_digest=p.environment_digest, task_set_digest=p.task_set_digest)


def manifest(candidate=d("candidate")):
    return IsolatedNeuralMemoryManifestRC14(
        candidate_digest=candidate, parent_epoch_digest=d("epoch"), base_model_digest=d("base"), tokenizer_digest=d("tok"),
        memory_artifact_digest=d("memory"), training_dataset_digest=d("train"), training_config_digest=d("cfg"),
        trainable_scope_digest=sha256_json(["isolated_memory.block.0", "isolated_memory.block.1"]), parameter_count=1_000_000, capacity_bytes=16_000_000,
    )


def proof(*, changed=("isolated_memory.block.0",)):
    return FrozenFoundationProofRC14(
        base_model_digest_before=d("base"), base_model_digest_after=d("base"), tokenizer_digest_before=d("tok"), tokenizer_digest_after=d("tok"),
        frozen_parameter_root_before=d("frozen-root"), frozen_parameter_root_after=d("frozen-root"),
        allowed_trainable_parameters=("isolated_memory.block.0", "isolated_memory.block.1"), observed_changed_parameters=changed,
    )


def test_preregistered_plan_rejects_cherry_picked_ablation_ladder():
    with pytest.raises(ValueError, match="complete fixed ablation"):
        PreregisteredContinualExperimentPlanRC14(
            experiment_id="bad", candidate_digest=d("c"), base_model_digest=d("b"), tokenizer_digest=d("t"), environment_digest=d("e"),
            task_set_digest=d("tasks"), hidden_task_commitment_digest=d("h"), variants=("frozen", "isolated_neural_memory"), seeds=(1, 2),
        )


def test_protocol_requires_complete_preregistered_matrix(tmp_path):
    store = PreregisteredContinualExperimentStoreRC14(tmp_path / "protocol"); p = plan(); store.seal(p)
    cert = store.certify(p.digest)
    assert not cert.complete and not cert.eligible and "incomplete_preregistered_matrix" in cert.reasons


def test_protocol_rejects_unregistered_seed_and_duplicate_replicate(tmp_path):
    store = PreregisteredContinualExperimentStoreRC14(tmp_path / "protocol"); p = plan(); store.seal(p)
    result = ContinualExperimentHarnessRC14().evaluate(measurement("frozen", gain=0.08))
    with pytest.raises(PermissionError, match="outside preregistered"):
        store.record_result(p.digest, variant="frozen", seed=999, result=result, evaluator_id="e", environment_digest=p.environment_digest, task_set_digest=p.task_set_digest)
    store.record_result(p.digest, variant="frozen", seed=11, result=result, evaluator_id="e", environment_digest=p.environment_digest, task_set_digest=p.task_set_digest)
    with pytest.raises(PermissionError, match="duplicate"):
        store.record_result(p.digest, variant="frozen", seed=11, result=result, evaluator_id="e", environment_digest=p.environment_digest, task_set_digest=p.task_set_digest)


def test_full_ablation_certificate_requires_incremental_l6_gain(tmp_path):
    store = PreregisteredContinualExperimentStoreRC14(tmp_path / "protocol"); p = plan(); store.seal(p); fill(store, p)
    cert = store.certify(p.digest)
    assert cert.complete and cert.eligible
    assert cert.incremental_gain_over_replay == pytest.approx(0.04)
    assert len(cert.replicate_digests) == len(DEFAULT_ABLATION_LADDER) * len(p.seeds)
    assert store.verify() == {"plans": 1, "replicates": 12}


def test_l6_ablation_rejects_no_incremental_value_over_replay(tmp_path):
    store = PreregisteredContinualExperimentStoreRC14(tmp_path / "protocol"); p = plan(); store.seal(p); fill(store, p, isolated_gain=0.12, replay_gain=0.12)
    cert = store.certify(p.digest)
    assert not cert.eligible and "incremental_gain_over_replay" in cert.reasons


def test_frozen_foundation_proof_rejects_scope_escape():
    q = IsolatedNeuralMemoryQualificationEngineRC14()
    p = plan(); cert = AblationQualificationCertificateRC14(p.digest, p.candidate_digest, (d("r"),), "isolated_neural_memory", 0.2, 0.1, 0.1, 0.01, 0.02, 0.99, True, True, ())
    out = q.qualify(plan=p, certificate=cert, manifest=manifest(), proof=proof(changed=("foundation.layer.0",)))
    assert not out.qualified and "trainable_scope_escape" in out.reasons


def test_isolated_neural_memory_qualification_requires_unchanged_foundation(tmp_path):
    store = PreregisteredContinualExperimentStoreRC14(tmp_path / "protocol"); p = plan(); store.seal(p); fill(store, p)
    cert = store.certify(p.digest)
    q = IsolatedNeuralMemoryQualificationEngineRC14()
    good = q.qualify(plan=p, certificate=cert, manifest=manifest(), proof=proof())
    assert good.qualified
    badproof = FrozenFoundationProofRC14(
        base_model_digest_before=d("base"), base_model_digest_after=d("mutated"), tokenizer_digest_before=d("tok"), tokenizer_digest_after=d("tok"),
        frozen_parameter_root_before=d("fr"), frozen_parameter_root_after=d("fr2"), allowed_trainable_parameters=("isolated_memory.block.0",),
        observed_changed_parameters=("isolated_memory.block.0",),
    )
    bad = q.qualify(plan=p, certificate=cert, manifest=manifest(), proof=badproof)
    assert not bad.qualified and "foundation_mutated" in bad.reasons


def test_qualification_engine_replays_experiment_evidence_instead_of_trusting_flag(tmp_path):
    candidate=d("candidate"); proposal_digest=d("proposal")
    store=PreregisteredContinualExperimentStoreRC14(tmp_path/"protocol"); p=plan(candidate); store.seal(p); fill(store,p)
    cert=store.certify(p.digest); m=manifest(candidate); fp=proof(); nq=IsolatedNeuralMemoryQualificationEngineRC14().qualify(plan=p,certificate=cert,manifest=m,proof=fp)
    artifacts=AuthorityArtifactStore(tmp_path/"artifacts")
    ev=ContinualExperimentEvidenceRC14(candidate,proposal_digest,p.digest,cert.digest,m.digest,fp.digest,nq.digest,store.head_digest(),asdict(m),asdict(fp),asdict(nq),True)
    ed=artifacts.put(ev)
    engine=QualificationEngineRC14(artifacts,PreregisteredPlanStore(tmp_path/"falsification"),GovernancePolicyRC14(),{},store)
    out=engine._verify_continual_experiment_evidence(ed,candidate_digest=candidate,proposal_digest=proposal_digest)
    assert out.digest==ed


def test_experiment_protocol_detects_payload_tamper(tmp_path):
    store=PreregisteredContinualExperimentStoreRC14(tmp_path/"protocol"); p=plan(); store.seal(p)
    result=ContinualExperimentHarnessRC14().evaluate(measurement("frozen",gain=0.08))
    store.record_result(p.digest,variant="frozen",seed=11,result=result,evaluator_id="e",environment_digest=p.environment_digest,task_set_digest=p.task_set_digest)
    with sqlite3.connect(store.db_path) as c:
        row=c.execute("SELECT payload_json FROM replicates WHERE seq=1").fetchone(); payload=json.loads(row[0]); payload["result"]["metrics"]["fresh_task_gain"]=999.0
        c.execute("UPDATE replicates SET payload_json=? WHERE seq=1",(json.dumps(payload,sort_keys=True,separators=(",",":")),)); c.commit()
    with pytest.raises(RuntimeError): store.verify()


def test_l6_qualification_requires_and_replays_empirical_evidence(tmp_path):
    policy = GovernancePolicyRC14(); artifacts = AuthorityArtifactStore(tmp_path / "artifacts")
    falsification = PreregisteredPlanStore(tmp_path / "falsification"); protocol = PreregisteredContinualExperimentStoreRC14(tmp_path / "protocol")
    proposal = LearningProposalRC14(
        target="isolated-memory:test", mechanism=LearningMechanism.SPARSE_EPISODIC_ADAPTER,
        coordinates=GovernanceCoordinates(PermanenceLevel.L6_ISOLATED_NEURAL_MEMORY, EvidenceStrength.E0_UNVERIFIED),
        evidence_digests=(d("source-evidence"),), rationale_digest=d("rationale"), proposer_id="researcher",
        production_identity_digest=d("production"), expected_gain=0.1,
    )
    cm = CandidateManifestRC14(proposal.digest, d("candidate-binary"), int(PermanenceLevel.L6_ISOLATED_NEURAL_MEMORY), policy.digest); cd = artifacts.put(cm)
    bm = BuildManifestRC14(cd, d("build-env"), d("build-output")); bd = artifacts.put(bm)

    ep = plan(cd); protocol.seal(ep); fill(protocol, ep)
    cert = protocol.certify(ep.digest); m = manifest(cd); fp = proof()
    nq = IsolatedNeuralMemoryQualificationEngineRC14().qualify(plan=ep, certificate=cert, manifest=m, proof=fp)
    experiment = ContinualExperimentEvidenceRC14(cd, proposal.digest, ep.digest, cert.digest, m.digest, fp.digest, nq.digest,
        protocol.head_digest(), asdict(m), asdict(fp), asdict(nq), True)
    experiment_digest = artifacts.put(experiment)

    cases = tuple(FalsificationCase(name, kind, d(name+"-payload"), d(name+"-expected")) for name, kind in (
        ("negative", FalsificationKind.NEGATIVE_CONTROL), ("retention", FalsificationKind.RETENTION),
        ("security", FalsificationKind.SECURITY), ("ood", FalsificationKind.OOD), ("fresh", FalsificationKind.FRESH_HIDDEN)))
    fplan = FalsificationPlan(cd, policy.digest, cases, "independent-planner"); falsification.seal(fplan)
    outcomes = tuple(FalsificationOutcome(c.case_id, c.digest, True, 1.0, d(c.case_id+"-evidence")) for c in cases)
    run = FalsificationRun(fplan.digest, cd, outcomes, "independent-evaluator", ep.environment_digest, ep.task_set_digest); falsification.record_run(run)
    evaluation = EvaluationBundleRC14(cd, bd, fplan.digest, run.digest, run.environment_digest); ed = artifacts.put(evaluation)

    verify_signer = Ed25519ReceiptSigner.generate(key_id="independent-verifier")
    replicate_signer = Ed25519ReceiptSigner.generate(key_id="replicator")
    def att(scope, signer, evidence_digest):
        body = {"schema":"egai-rc14-evidence-attestation-v1","scope":scope,"candidate_digest":cd,
                "evaluation_digest":ed,"evidence_digest":evidence_digest,"issuer_id":signer.key_id}
        return artifacts.put(EvidenceAttestationRC14(scope, cd, ed, evidence_digest, signer.key_id, signer.issue(body)))
    a1 = att("independent_verification", verify_signer, d("independent-proof"))
    a2 = att("replication", replicate_signer, d("replication-proof"))

    engine = QualificationEngineRC14(artifacts, falsification, policy,
        {"independent_verification": verify_signer.verifier(), "replication": replicate_signer.verifier()}, protocol)
    with pytest.raises(PermissionError, match="preregistered continual-experiment evidence"):
        engine.build_and_require(proposal, candidate_digest=cd, evaluation_digest=ed, attestation_digests=(a1, a2))
    record = engine.build_and_require(proposal, candidate_digest=cd, evaluation_digest=ed,
        attestation_digests=(a1, a2), continual_experiment_evidence_digest=experiment_digest)
    assert record.fresh_ood_validated and record.replicated
    assert record.continual_experiment_evidence_digest == experiment_digest
