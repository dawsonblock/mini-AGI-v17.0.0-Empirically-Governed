from egai.bench.preregistration import PreregistrationAuthority
from egai.bench.ablation_protocol import AblationResult,decide_incremental
from egai.common.canonical import digest
from egai.common.crypto import Ed25519Signer,Ed25519Verifier
from egai.common.trust import AuthorityTrust


def test_preregistration_is_signed_and_bound():
    s=Ed25519Signer.generate('bench');v=Ed25519Verifier();v.register(s.key_id,s.public_bytes())
    t=AuthorityTrust({'benchmark':(s.key_id,)})
    a=PreregistrationAuthority('registry',s,v,t)
    p=a.create('exp','Frozen memory+skills improve R4/R5 transfer',digest({'m':1}),digest({'e':1}),digest({'h':1}))
    assert a.verify(p)
    assert p.primary_metric=='R4_R5_forward_transfer'


def test_ablation_must_add_transfer_without_breaking_hard_gates():
    b0=AblationResult('B0_FROZEN',.10,1,1,1,1,True)
    b1=AblationResult('B1_EPISODIC',.15,1,1,1,1.2,True)
    b2=AblationResult('B2_PROCEDURAL',.14,1,1,1,1.4,True)
    assert decide_incremental(None,b0).advance
    assert decide_incremental(b0,b1).advance
    assert not decide_incremental(b1,b2).advance
