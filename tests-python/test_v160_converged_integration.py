from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from egai.common.canonical import digest
from egai.common.crypto import Ed25519Signer, Ed25519Verifier
from egai.common.trust import AuthorityTrust
from minagi.integration.qw3_state import RuntimeStateMismatch, ServedArtifactManifest
from minagi.v14.adaptive_v149 import (
    EmpiricalPlasticityPolicyV149,
    EmpiricalPlasticityRouterV149,
    PlasticityExperimentCommitmentV149,
    PlasticityMechanismV149,
)
from minagi.v16.control_plane import (
    ConvergedEvidenceBundleV160,
    IndependentConvergedQualifierV160,
)
from minagi.v16.dream_stats import (
    StatisticalDreamQualifierV160,
    compare_replicated_live_canary_v160,
)
from minagi.v16.isolated_solver import IsolatedJSONSolverV160
from minagi.v16.plasticity_execution import (
    MechanismExecutionResultV160,
    PlasticityExecutionHarnessV160,
    PlasticityTrialMetricsV160,
)
from minagi.v16.runtime_closure2 import (
    FullMeasuredGovernedServingContract,
    MeasuredRuntimeClosureV2,
)

ZERO = "0" * 64


def _raw_digest(tag: str) -> str:
    return digest({"tag": tag}).split(":", 1)[1]


def _manifest(tmp_path: Path) -> tuple[ServedArtifactManifest, dict[str, Path]]:
    paths = {}
    for name, payload in {
        "model": b"model-v1601",
        "tokenizer": b"tokenizer-v1601",
        "runtime": b"runtime-v1601",
        "retrieval": b"retrieval-v1601",
        "skill": b"skill-v1601",
    }.items():
        path = tmp_path / name
        path.write_bytes(payload)
        paths[name] = path
    import hashlib
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = ServedArtifactManifest(
        epoch_digest=digest({"epoch": 1601}),
        runtime_manifest_digest=digest({"runtime-manifest": 1601}),
        foundation_digest=h(paths["model"]),
        tokenizer_digest=h(paths["tokenizer"]),
        kv_archive_root=ZERO,
        adapter_set_root=_raw_digest("adapter"),
        retrieval_policy_root=h(paths["retrieval"]),
        skill_policy_root=h(paths["skill"]),
        runtime_binary_digest=h(paths["runtime"]),
        native_adapter_bundle_root=ZERO,
    )
    return manifest, paths


def test_runtime_closure2_measures_all_file_backed_roots(tmp_path):
    manifest, p = _manifest(tmp_path)
    closure = MeasuredRuntimeClosureV2.from_files(
        manifest=manifest,
        model_path=p["model"],
        tokenizer_path=p["tokenizer"],
        runtime_binary_path=p["runtime"],
        retrieval_policy_path=p["retrieval"],
        skill_policy_path=p["skill"],
    )
    assert closure.tokenizer_digest == manifest.tokenizer_digest
    assert closure.retrieval_policy_root == manifest.retrieval_policy_root
    assert closure.skill_policy_root == manifest.skill_policy_root
    args = closure.qw3_args(
        manifest=manifest,
        tokenizer_path=p["tokenizer"],
        retrieval_policy_path=p["retrieval"],
        skill_policy_path=p["skill"],
    )
    assert "--state-tokenizer-path" in args
    assert "--state-retrieval-policy-path" in args
    assert "--state-skill-policy-path" in args


def test_runtime_closure2_rejects_policy_tamper(tmp_path):
    manifest, p = _manifest(tmp_path)
    p["retrieval"].write_bytes(b"tampered")
    with pytest.raises(RuntimeStateMismatch, match="retrieval_policy_root"):
        MeasuredRuntimeClosureV2.from_files(
            manifest=manifest,
            model_path=p["model"],
            tokenizer_path=p["tokenizer"],
            runtime_binary_path=p["runtime"],
            retrieval_policy_path=p["retrieval"],
            skill_policy_path=p["skill"],
        )


def test_runtime_closure2_contract_requires_native_measurements(tmp_path):
    manifest, p = _manifest(tmp_path)
    closure = MeasuredRuntimeClosureV2.from_files(
        manifest=manifest,
        model_path=p["model"], tokenizer_path=p["tokenizer"], runtime_binary_path=p["runtime"],
        retrieval_policy_path=p["retrieval"], skill_policy_path=p["skill"],
    )
    class Lease:
        epoch_digest = manifest.epoch_digest
    state = {
        "governed": True,
        "epoch_id": manifest.epoch_digest,
        "manifest_digest": manifest.manifest_digest,
        "artifact_root": manifest.artifact_root,
        "adapter_set_root": manifest.adapter_set_root,
        "runtime_closure_verified": True,
        "runtime_closure_digest": closure.digest,
        "measured_foundation_digest": manifest.foundation_digest,
        "measured_runtime_binary_digest": manifest.runtime_binary_digest,
        "measured_kvmem_archive_root": manifest.kv_archive_root,
        "measured_tokenizer_digest": manifest.tokenizer_digest,
        "measured_retrieval_policy_root": manifest.retrieval_policy_root,
        "measured_skill_policy_root": manifest.skill_policy_root,
    }
    c = FullMeasuredGovernedServingContract(base_url="http://unused", fetch_json=lambda _: state)
    assert c.verify_loaded_state(lease=Lease(), manifest=manifest).runtime_closure_verified
    bad = dict(state); bad["measured_skill_policy_root"] = "f" * 64
    c = FullMeasuredGovernedServingContract(base_url="http://unused", fetch_json=lambda _: bad)
    with pytest.raises(RuntimeStateMismatch, match="measured_skill_policy_root"):
        c.verify_loaded_state(lease=Lease(), manifest=manifest)


def test_plasticity_execution_runs_least_permanent_first_and_stops():
    policy = EmpiricalPlasticityPolicyV149(min_success_rate=0.8, min_retention=0.9, max_compute_cost=10.0)
    router = EmpiricalPlasticityRouterV149(policy)
    commitment = PlasticityExperimentCommitmentV149(
        request_digest=digest({"request": 1}), evaluator_id="independent-evaluator", run_id="run-1",
        policy_digest=policy.digest,
        ordered_mechanisms=(PlasticityMechanismV149.CURRENT_CONTEXT, PlasticityMechanismV149.RETRIEVAL),
    )
    calls = []
    def runner(mechanism, request_digest):
        calls.append(mechanism)
        return MechanismExecutionResultV160(
            mechanism=mechanism, artifact={"m": mechanism.value}, artifact_digest=digest({"artifact": mechanism.value}),
            predicted_success_rate=0.8, predicted_interference=0.01, predicted_compute_cost=0.1,
        )
    def evaluator(result, request_digest):
        success = 0.5 if result.mechanism is PlasticityMechanismV149.CURRENT_CONTEXT else 0.95
        return PlasticityTrialMetricsV160(
            success_rate=success, retention=0.99, interference=0.0, compute_cost=0.1,
            causal_ablated_success_rate=max(0.0, success - 0.10), evidence_digests=(digest({"eval": result.mechanism.value}),),
        )
    harness = PlasticityExecutionHarnessV160(router)
    report, calibration, attempts, trial_digests = harness.run(
        commitment=commitment,
        mechanism_runners={m: runner for m in commitment.ordered_mechanisms},
        evaluator=evaluator,
    )
    assert calls == list(commitment.ordered_mechanisms)
    assert report.decision == "PASS"
    assert report.selected_mechanism == PlasticityMechanismV149.RETRIEVAL.value
    assert len(attempts) == 2 and len(trial_digests) == 2
    assert calibration.attempt_digests == tuple(a.digest for a in attempts)


def test_converged_qualifier_fail_closed_for_search_and_foundation_changes():
    signer = Ed25519Signer.generate("qualifier-key")
    verifier = Ed25519Verifier(); verifier.register(signer.key_id, signer.public_bytes())
    trust = AuthorityTrust({"evaluator": (signer.key_id,)})
    good = {digest({"ok": x}) for x in ("plasticity", "transfer", "runtime", "dream")}
    plasticity, transfer, runtime, dream = tuple(good)
    q = IndependentConvergedQualifierV160(
        evaluator_id="q1", signer=signer, verifier=verifier, trust=trust,
        plasticity_verifier=lambda d: d == plasticity,
        forward_transfer_verifier=lambda d: d == transfer,
        runtime_closure_verifier=lambda d: d == runtime,
        dream_verifier=lambda d: d == dream,
    )
    base = dict(
        candidate_digest=digest({"candidate": 1}), request_digest=digest({"request": 1}),
        plasticity_report_digest=plasticity, forward_transfer_receipt_digest=transfer,
        runtime_closure_digest=runtime,
    )
    missing_dream = q.qualify(evidence=ConvergedEvidenceBundleV160(**base, search_policy_changed=True))
    assert not missing_dream.passed and not missing_dream.gates["dream_search_qualification"]
    foundation = q.qualify(evidence=ConvergedEvidenceBundleV160(**base, foundation_changed=True))
    assert not foundation.passed and not foundation.gates["foundation_update_policy"]
    passed = q.qualify(evidence=ConvergedEvidenceBundleV160(
        **base, search_policy_changed=True, dream_qualification_digest=dream,
    ))
    assert passed.passed and q.verify(passed)


def test_dream_statistical_qualifier_requires_replicated_nonregression():
    class FakeEvaluator:
        def __init__(self, seed): self.seed = seed
        def evaluate(self, worlds, policy):
            # candidate beats baseline by a stable margin on every seed
            score = (1.0 if policy.policy_id == "candidate" else 0.8) + self.seed * 0.0001
            return SimpleNamespace(score=score, mean_support_ratio=1.0, mean_uncertainty=0.1), []
    candidate = SimpleNamespace(policy_id="candidate")
    baseline = SimpleNamespace(policy_id="baseline")
    candidate_meta = SimpleNamespace(policy_id="candidate", version="1", source_digest="abc", config={}, parent_policy_id=None)
    # use the real CandidatePolicy dataclass for canonical asdict support
    from dream_rsi_governed.models import CandidatePolicy
    candidate_meta = CandidatePolicy("candidate", "1", "source")
    worlds = [SimpleNamespace(world_id=str(i)) for i in range(3)]
    qualifier = StatisticalDreamQualifierV160(lambda seed: FakeEvaluator(seed), bootstrap_samples=400)
    result = qualifier.qualify(
        candidate_meta=candidate_meta, candidate=candidate, baseline=baseline,
        holdout_worlds=worlds, seeds=(1, 2, 3, 4),
    )
    assert result.passed
    assert result.delta_ci_low > 0


def test_replicated_canary_uses_paired_ci_and_cost_gate():
    att = compare_replicated_live_canary_v160(
        candidate_policy_id="c", baseline_policy_id="b",
        run_candidate=lambda seed: (1.0 + seed * 0.001, 1.0),
        run_baseline=lambda seed: (0.8 + seed * 0.001, 1.0),
        environment_digest=digest({"env": 1}), seeds=(1, 2, 3, 4), bootstrap_samples=400,
    )
    assert att.passed and att.score_delta_ci_low > 0
    expensive = compare_replicated_live_canary_v160(
        candidate_policy_id="c", baseline_policy_id="b",
        run_candidate=lambda seed: (1.0, 2.0), run_baseline=lambda seed: (0.8, 1.0),
        environment_digest=digest({"env": 1}), seeds=(1, 2, 3), bootstrap_samples=200,
    )
    assert not expensive.passed


def test_isolated_solver_protocol_does_not_send_expected_answer(tmp_path):
    solver_py = tmp_path / "solver.py"
    solver_py.write_text(
        "import json,sys\n"
        "r=json.load(sys.stdin)\n"
        "assert set(r)=={'case_id','input','task_kind'}\n"
        "json.dump({'text': r['input'][::-1]}, sys.stdout)\n"
    )
    solver = IsolatedJSONSolverV160([sys.executable, str(solver_py)])
    assert solver.solve(case_id="case-1", input_text="abc", task_kind="reverse") == "cba"

