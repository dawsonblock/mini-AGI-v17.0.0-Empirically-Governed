import json
import sqlite3

import pytest

from minagi.egai.canonical import sha256_json
from minagi.rc14 import (
    AdaptiveReplayScheduler,
    BeliefEvidenceSignal,
    ContinualExperimentHarnessRC14,
    ContinualExperimentLedgerRC14,
    ContinualExperimentMeasurement,
    CrossTaskSkillInductionEngine,
    HeldOutSkillEvaluationRC14,
    ReplayMemorySignalRC14,
    SemanticBeliefRevisionEngine,
    VerifiedSkillEpisodeRC14,
)


def d(x):
    return sha256_json({"x": x})


def test_semantic_belief_revision_caps_correlated_source_and_detects_conflict():
    engine = SemanticBeliefRevisionEngine(min_distinct_sources=2, contested_margin=0.20)
    proposal = engine.propose(
        belief_id="b-weather",
        statement_digest=d("statement"),
        production_identity_digest=d("prod"),
        signals=(
            BeliefEvidenceSignal(d("s1-weak"), "source-A", "support", 0.2),
            BeliefEvidenceSignal(d("s1-strong"), "source-A", "support", 0.9),
            BeliefEvidenceSignal(d("c1"), "source-B", "contradict", 0.85),
        ),
    )
    assert proposal.support_digests == (d("s1-strong"),)
    assert proposal.contradiction_digests == (d("c1"),)
    assert proposal.disposition == "contested"
    assert proposal.candidate.status.value == "candidate"
    assert engine.can_promote is False


def test_semantic_belief_revision_requires_independent_sources():
    engine = SemanticBeliefRevisionEngine(min_distinct_sources=2)
    with pytest.raises(PermissionError, match="independent-source"):
        engine.propose(
            belief_id="b",
            statement_digest=d("statement"),
            production_identity_digest=d("prod"),
            signals=(BeliefEvidenceSignal(d("a"), "same-source", "support", 0.9),),
        )


def _episode(i, family, verifier, root):
    return VerifiedSkillEpisodeRC14(
        episode_id=f"e{i}", task_family=family, procedure_digest=d("procedure"), evidence_root=d(root),
        verification_receipt_digest=d(f"receipt-{i}"), verifier_id=verifier, score=0.95,
    )


def test_cross_task_skill_induction_requires_fresh_unseen_transfer():
    engine = CrossTaskSkillInductionEngine(min_transfer_gain=0.05)
    episodes = (_episode(1, "sorting", "v1", "r1"), _episode(2, "routing", "v2", "r2"), _episode(3, "sorting", "v1", "r1"))
    heldout = (
        HeldOutSkillEvaluationRC14("h1", "scheduling", d("procedure"), 0.40, 0.55, d("h1-r"), "v3", fresh=True),
    )
    candidate = engine.induce(episodes, heldout)
    assert candidate.training_task_families == ("routing", "sorting")
    assert candidate.heldout_task_families == ("scheduling",)
    assert candidate.min_heldout_transfer_gain == pytest.approx(0.15)
    manifest = candidate.to_skill_manifest(skill_id="skill-x", version=1, name="cross-task procedure", activation_conditions=("task",))
    assert manifest.implementation_digest == d("procedure")
    assert engine.can_promote is False


def test_skill_induction_rejects_seen_family_as_heldout():
    engine = CrossTaskSkillInductionEngine()
    episodes = (_episode(1, "a", "v1", "r1"), _episode(2, "b", "v2", "r2"), _episode(3, "a", "v1", "r1"))
    heldout = (HeldOutSkillEvaluationRC14("h", "a", d("procedure"), 0.1, 0.9, d("hr"), "v3"),)
    with pytest.raises(PermissionError, match="disjoint"):
        engine.induce(episodes, heldout)


def test_adaptive_replay_batch_prioritizes_risk_and_preserves_family_diversity():
    scheduler = AdaptiveReplayScheduler(min_priority=0.5, model_time_interval=100.0)
    signals = (
        ReplayMemorySignalRC14("a1", "A", 0.9, 0.9, interference_risk=0.9),
        ReplayMemorySignalRC14("a2", "A", 0.8, 0.8, interference_risk=0.8),
        ReplayMemorySignalRC14("b1", "B", 0.7, 0.7, interference_risk=0.7),
    )
    batch = scheduler.rank_batch(signals, model_time=1.0, max_items=2, max_per_task_family=1)
    assert batch.memory_ids == ("a1", "b1")
    assert batch.task_families == ("A", "B")
    assert batch.priorities[0] > batch.priorities[1]


def good_measurement(variant="full"):
    return ContinualExperimentMeasurement(
        variant=variant,
        old_task_history={"A": (0.8, 0.9), "B": (0.75, 0.8)},
        old_task_before={"A": 0.88, "B": 0.79},
        old_task_after={"A": 0.87, "B": 0.78},
        fresh_history_score=0.72,
        fresh_frozen_baseline_score=0.60,
        falsification_survival=1.0,
        security_regressions=0,
        unauthorized_writes=0,
        memory_growth=10.0,
        compute_cost=2.0,
        latency_delta=0.01,
        reproducibility=0.95,
    )


def test_continual_experiment_harness_measures_transfer_forgetting_and_eligibility():
    harness = ContinualExperimentHarnessRC14(max_mean_forgetting=0.05, max_worst_forgetting=0.05, min_fresh_task_gain=0.05)
    result = harness.evaluate(good_measurement())
    assert result.metrics.fresh_task_gain == pytest.approx(0.12)
    assert result.metrics.mean_forgetting == pytest.approx((0.03 + 0.02) / 2)
    assert result.metrics.backward_transfer == pytest.approx(-0.01)
    assert result.eligible_for_promotion_evidence is True


def test_continual_experiment_rejects_gain_that_forgets_old_tasks():
    harness = ContinualExperimentHarnessRC14(max_mean_forgetting=0.05, max_worst_forgetting=0.10, min_fresh_task_gain=0.05)
    m = ContinualExperimentMeasurement(
        variant="catastrophic",
        old_task_history={"A": (0.95,), "B": (0.90,)},
        old_task_before={"A": 0.95, "B": 0.90},
        old_task_after={"A": 0.50, "B": 0.55},
        fresh_history_score=0.99, fresh_frozen_baseline_score=0.50,
        falsification_survival=1.0, reproducibility=1.0,
    )
    result = harness.evaluate(m)
    assert result.metrics.fresh_task_gain > 0.4
    assert result.eligible_for_promotion_evidence is False
    assert "mean_forgetting" in result.rejection_reasons
    assert "worst_case_forgetting" in result.rejection_reasons


def test_continual_experiment_ledger_is_hash_chained_and_detects_tamper(tmp_path):
    harness = ContinualExperimentHarnessRC14()
    ledger = ContinualExperimentLedgerRC14(tmp_path / "science")
    m = good_measurement()
    result = harness.evaluate(m)
    ledger.append(m, result)
    assert ledger.verify()["experiments"] == 1
    with sqlite3.connect(ledger.db_path) as c:
        row = c.execute("SELECT payload_json FROM events WHERE seq=1").fetchone()
        payload = json.loads(row[0]); payload["measurement"]["fresh_history_score"] = 999.0
        c.execute("UPDATE events SET payload_json=? WHERE seq=1", (json.dumps(payload, sort_keys=True, separators=(",", ":")),)); c.commit()
    with pytest.raises(RuntimeError, match="measurement digest"):
        ledger.verify()


def test_ablation_comparison_reports_incremental_effects():
    harness = ContinualExperimentHarnessRC14(max_mean_forgetting=1.0, max_worst_forgetting=1.0, min_falsification_survival=0.0)
    baseline = harness.evaluate(good_measurement("frozen"))
    better_m = ContinualExperimentMeasurement(**{**good_measurement("full").__dict__, "fresh_history_score": 0.80})
    better = harness.evaluate(better_m)
    table = harness.compare({"frozen": baseline, "full": better}, baseline="frozen")
    assert table["full"]["delta_fresh_task_gain"] == pytest.approx(0.08)
