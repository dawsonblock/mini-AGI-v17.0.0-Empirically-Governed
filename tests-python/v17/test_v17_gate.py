from minagi.v17 import AuthorityIdentity, EmpiricalQualificationBundle, V17PromotionGate

def ident(n): return AuthorityIdentity(n, n+"-key", n+"-proc")

def test_full_bundle_passes():
    b=EmpiricalQualificationBundle(True,True,True,True,True,True,0,True,ident("proposer"),ident("qualifier"),ident("promoter"))
    assert V17PromotionGate.qualify(b)

def test_shared_authority_fails():
    a=ident("same")
    b=EmpiricalQualificationBundle(True,True,True,True,True,True,0,True,a,a,ident("promoter"))
    assert not V17PromotionGate.qualify(b)

def test_missing_evidence_fails():
    b=EmpiricalQualificationBundle(True,False,True,True,True,True,0,True,ident("proposer"),ident("qualifier"),ident("promoter"))
    assert not V17PromotionGate.qualify(b)
