from dataclasses import asdict
import pytest

from egai.authority.replay_policy import GroundedReplayPolicyAuthority, ReplayPolicyGate, ReplayPolicyPlanRegistrar
from egai.common.artifacts import ArtifactStore
from egai.common.canonical import digest
from egai.common.crypto import Ed25519Signer, Ed25519Verifier
from egai.common.trust import AuthorityTrust
from egai.replay.policy import GroundedOutcome, GroundedReplayEpisode, PolicyDecision, ReplayObjective, ReplayRound, PrefixOnlyPolicyEvaluator
from egai.replay.vault import ReplayHistoryVault


def make_episode(i):
    rounds = []
    for t in range(2):
        rounds.append(ReplayRound(
            t,
            digest({"ep": i, "t": t, "visible": True}),
            ("good", "bad"),
            (
                GroundedOutcome("good", 1.0, f"evidence-{i}-{t}-good", {}),
                GroundedOutcome("bad", 0.0, f"evidence-{i}-{t}-bad", {}),
            ),
        ))
    return GroundedReplayEpisode(f"ep-{i}", tuple(rounds), 2.0)


def baseline(view):
    return PolicyDecision(("bad",))


def candidate(view):
    return PolicyDecision(("good",))


def test_prefix_view_never_exposes_unselected_or_future_outcomes():
    seen = []
    def p(view):
        seen.append(view)
        return PolicyDecision(("good",))
    result = PrefixOnlyPolicyEvaluator(ReplayObjective()).evaluate_episode(make_episode(0), p)
    assert result.best_quality == 1.0
    assert seen[0].observed_results == ()
    assert len(seen[1].observed_results) == 1
    assert seen[1].observed_results[0].action_id == "good"
    assert not hasattr(seen[0], "outcomes")


def test_illegal_action_fails_closed():
    def p(view):
        return PolicyDecision(("future-secret-action",))
    with pytest.raises(PermissionError):
        PrefixOnlyPolicyEvaluator().evaluate_episode(make_episode(0), p)


def test_replay_vault_hides_plaintext_and_wrong_key_fails():
    eps = tuple(make_episode(i) for i in range(12))
    key = ReplayHistoryVault.generate_key()
    sealed = ReplayHistoryVault.seal("holdout", 1, eps, key)
    assert "evidence-0-0-good" not in str(asdict(sealed))
    assert len(ReplayHistoryVault.open(sealed, key)) == 12
    with pytest.raises(Exception):
        ReplayHistoryVault.open(sealed, ReplayHistoryVault.generate_key())


def test_offline_policy_qualification_is_signed_but_not_deployable(tmp_path):
    bench = Ed25519Signer.generate("bench")
    ev = Ed25519Signer.generate("eval")
    verifier = Ed25519Verifier()
    verifier.register(bench.key_id, bench.public_bytes())
    verifier.register(ev.key_id, ev.public_bytes())
    trust = AuthorityTrust({"benchmark": (bench.key_id,), "evaluator": (ev.key_id,)})
    eps = tuple(make_episode(i) for i in range(12))
    key = ReplayHistoryVault.generate_key()
    sealed = ReplayHistoryVault.seal("holdout", 1, eps, key)
    objective = ReplayObjective(attempt_cost=.01, round_cost=.001)
    gate = ReplayPolicyGate(bootstrap_samples=200, min_mean_gain=.1, min_win_rate=.8, max_loss_rate=0.0, min_holdout_episodes=12)
    plan = ReplayPolicyPlanRegistrar("registrar", bench).register(
        "rp1", sealed.sealed_digest, digest({"p": "base"}), digest({"p": "candidate"}), objective, gate
    )
    auth = GroundedReplayPolicyAuthority("evaluator", ev, verifier, trust, ArtifactStore(tmp_path / "artifacts"))
    receipt = auth.evaluate("rr1", plan, sealed, key, baseline, candidate)
    assert receipt.qualified_offline
    assert receipt.requires_live_canary
    assert not receipt.deployable
    assert auth.verify_receipt(receipt)
    assert receipt.gates["positive_ci"] and receipt.gates["significance"]


def test_grounded_outcome_requires_evidence():
    with pytest.raises(ValueError):
        GroundedOutcome("a", 1.0, "", {})

from egai.authority.replay_canary import LiveCanaryCase, LiveCanaryGate, ReplayLiveCanaryAuthority


def _offline_receipt_for_canary(tmp_path):
    bench = Ed25519Signer.generate("bench")
    ev = Ed25519Signer.generate("eval")
    verifier = Ed25519Verifier()
    verifier.register(bench.key_id, bench.public_bytes())
    verifier.register(ev.key_id, ev.public_bytes())
    trust = AuthorityTrust({"benchmark": (bench.key_id,), "evaluator": (ev.key_id,)})
    eps = tuple(make_episode(i) for i in range(12))
    key = ReplayHistoryVault.generate_key()
    sealed = ReplayHistoryVault.seal("holdout", 1, eps, key)
    plan = ReplayPolicyPlanRegistrar("registrar", bench).register(
        "rp-canary", sealed.sealed_digest, digest({"p": "base"}), digest({"p": "candidate"}),
        ReplayObjective(), ReplayPolicyGate(bootstrap_samples=200, min_mean_gain=.1, min_win_rate=.8, max_loss_rate=0.0),
    )
    offline_auth = GroundedReplayPolicyAuthority("offline-eval", ev, verifier, trust, ArtifactStore(tmp_path / "artifacts"))
    receipt = offline_auth.evaluate("off", plan, sealed, key, baseline, candidate)
    return ev, verifier, trust, receipt


def test_live_canary_required_after_offline_qualification(tmp_path):
    ev, verifier, trust, offline = _offline_receipt_for_canary(tmp_path)
    cases = [LiveCanaryCase(f"c{i}", 0.5, 0.8, f"evidence-live-{i}") for i in range(20)]
    canary = ReplayLiveCanaryAuthority("live-eval", ev, verifier, trust).evaluate(
        "live-r", offline, cases, LiveCanaryGate(min_cases=20, min_mean_gain=.1, max_loss_rate=0.0)
    )
    assert canary.passed and canary.promotion_eligible
    assert not canary.deployable


def test_live_canary_security_regression_blocks_promotion_eligibility(tmp_path):
    ev, verifier, trust, offline = _offline_receipt_for_canary(tmp_path)
    cases = [LiveCanaryCase(f"c{i}", 0.5, 0.8, f"evidence-live-{i}", security_ok=(i != 3)) for i in range(20)]
    canary = ReplayLiveCanaryAuthority("live-eval", ev, verifier, trust).evaluate("live-r", offline, cases)
    assert not canary.passed
    assert not canary.promotion_eligible
