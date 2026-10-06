from dream_rsi_governed.evaluator import ReplayEvaluator
from dream_rsi_governed.models import Action, CandidatePolicy, Outcome, ReplayDecision, ReplayNode, ReplayWorld
from dream_rsi_governed.policy import FixedBreadthPolicy
from dream_rsi_governed.replay import ReplayEngine
from minagi.v16.dream_stats import StatisticalDreamQualifierV160, compare_replicated_live_canary_v160


class HighPolicy:
    policy_id = 'high-policy-v1'
    def decide(self, context):
        if not context.legal_actions: return ReplayDecision((), stop=True)
        best = sorted(context.legal_actions, key=lambda a: a.id)[-1]
        return ReplayDecision((best.id,))


def _world(i):
    low=Action('a-low','a',metadata={'support':1.0}); high=Action('z-high','z',metadata={'support':1.0})
    return ReplayWorld(f'w{i}',f't{i}',(
        ReplayNode(low,(Outcome(low.id,.1),Outcome(low.id,.2))),
        ReplayNode(high,(Outcome(high.id,.9),Outcome(high.id,1.0))),
    ),budget=1,max_parallelism=1)


def test_replicated_dream_qualification_requires_positive_paired_ci():
    q=StatisticalDreamQualifierV160(lambda seed: ReplayEvaluator(ReplayEngine(seed=seed)),bootstrap_samples=300)
    candidate=HighPolicy(); baseline=FixedBreadthPolicy(); meta=CandidatePolicy(candidate.policy_id,'1','sha256:'+'1'*64)
    r=q.qualify(candidate_meta=meta,candidate=candidate,baseline=baseline,holdout_worlds=[_world(i) for i in range(4)],seeds=(1,2,3,4,5,6))
    assert r.passed
    assert r.delta_ci_low > 0


def test_replicated_canary_uses_ci_not_single_lucky_run():
    r=compare_replicated_live_canary_v160(
        candidate_policy_id='c',baseline_policy_id='b',environment_digest='sha256:'+'2'*64,
        seeds=(1,2,3,4),run_candidate=lambda s:(1.0,1.0),run_baseline=lambda s:(0.5,1.0),bootstrap_samples=200,
    )
    assert r.passed and r.score_delta_ci_low > 0
