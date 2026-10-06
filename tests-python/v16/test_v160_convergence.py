from __future__ import annotations

import sys
from dataclasses import asdict

import pytest

from egai.common.canonical import digest
from egai.common.crypto import Ed25519Signer, Ed25519Verifier
from egai.common.trust import AuthorityTrust
from minagi.v14.adaptive_v149 import (
    EmpiricalPlasticityPolicyV149,
    EmpiricalPlasticityRouterV149,
    PlasticityExperimentCommitmentV149,
    PlasticityMechanismV149 as M,
)
from minagi.v16.control_plane import (
    ConvergedEvidenceBundleV160,
    IndependentConvergedQualifierV160,
)
from minagi.v16.isolated_solver import IsolatedJSONSolverV160
from minagi.v16.plasticity_execution import (
    MechanismExecutionResultV160,
    PlasticityExecutionHarnessV160,
    PlasticityTrialMetricsV160,
)


def test_plasticity_harness_executes_in_order_and_stops_at_first_sufficient():
    policy = EmpiricalPlasticityPolicyV149()
    router = EmpiricalPlasticityRouterV149(policy)
    c = PlasticityExperimentCommitmentV149(
        request_digest=digest({"request": 1}),
        evaluator_id="independent-eval",
        run_id="run-1",
        policy_digest=policy.digest,
        ordered_mechanisms=(M.CURRENT_CONTEXT, M.RETRIEVAL, M.EPISODIC_MEMORY),
    )
    seen = []

    def runner(mechanism, request_digest):
        seen.append(mechanism)
        return MechanismExecutionResultV160(
            mechanism=mechanism,
            artifact={"mechanism": mechanism.value},
            artifact_digest=digest({"artifact": mechanism.value}),
            predicted_success_rate=.5,
            predicted_interference=.01,
            predicted_compute_cost=.1,
        )

    def evaluator(result, request_digest):
        passed = result.mechanism is M.RETRIEVAL
        return PlasticityTrialMetricsV160(
            success_rate=.95 if passed else .4,
            retention=1.0,
            interference=.0,
            compute_cost=.1,
            causal_ablated_success_rate=.60 if passed else .39,
            evidence_digests=(digest({"eval": result.mechanism.value}),),
        )

    report, calibration, attempts, execution = PlasticityExecutionHarnessV160(router).run(
        commitment=c,
        mechanism_runners={m: runner for m in c.ordered_mechanisms},
        evaluator=evaluator,
    )
    assert report.decision == "PASS"
    assert report.selected_mechanism == "retrieval"
    assert seen == [M.CURRENT_CONTEXT, M.RETRIEVAL]
    assert len(attempts) == len(execution) == 2
    assert calibration.attempt_digests == tuple(a.digest for a in attempts)


def test_converged_qualifier_resolves_evidence_by_digest_and_cannot_self_promote():
    signer = Ed25519Signer.generate("converged-evaluator")
    verifier = Ed25519Verifier(); verifier.register(signer.key_id, signer.public_bytes())
    trust = AuthorityTrust({"evaluator": (signer.key_id,)})
    good = {digest({"plasticity": 1}), digest({"transfer": 1}), digest({"runtime": 1}), digest({"dream": 1})}
    evidence = ConvergedEvidenceBundleV160(
        candidate_digest=digest({"candidate": 1}),
        request_digest=digest({"request": 1}),
        plasticity_report_digest=digest({"plasticity": 1}),
        forward_transfer_receipt_digest=digest({"transfer": 1}),
        runtime_closure_digest=digest({"runtime": 1}),
        dream_qualification_digest=digest({"dream": 1}),
        search_policy_changed=True,
    )
    q = IndependentConvergedQualifierV160(
        evaluator_id="eval",
        signer=signer,
        verifier=verifier,
        trust=trust,
        plasticity_verifier=lambda d: d in good,
        forward_transfer_verifier=lambda d: d in good,
        runtime_closure_verifier=lambda d: d in good,
        dream_verifier=lambda d: d in good,
    )
    receipt = q.qualify(evidence=evidence)
    assert receipt.passed
    assert q.verify(receipt)
    # Qualification contains no served manifest or mutation method; promotion is separate.
    assert not hasattr(q, "promote")


def test_isolated_solver_json_boundary_hides_expected_answer():
    code = (
        "import json,sys; r=json.loads(sys.stdin.read()); "
        "assert 'expected' not in r; assert set(r)=={'case_id','input','task_kind'}; "
        "print(json.dumps({'text':'OK' if r['input']=='x' else 'MISS'}))"
    )
    solver = IsolatedJSONSolverV160((sys.executable, "-c", code))
    assert solver.solve(case_id="c", input_text="x", task_kind="code") == "OK"
