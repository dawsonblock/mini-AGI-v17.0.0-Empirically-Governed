from egai.common.canonical import digest
from kvcontinual.governance.causal_credit import CausalCreditAssigner

def test_causal_credit_positive_uplift():
    r=CausalCreditAssigner().assess('i',[0]*10,[1]*10,'skill',digest({'ctx':1}),samples=100,seed=2);assert r.effect.mean_gain==1 and r.record_digest.startswith('sha256:')
