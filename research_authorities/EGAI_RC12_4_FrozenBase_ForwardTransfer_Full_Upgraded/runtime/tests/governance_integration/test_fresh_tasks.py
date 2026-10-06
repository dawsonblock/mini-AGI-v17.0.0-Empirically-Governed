from egai.common.crypto import Ed25519Signer,Ed25519Verifier
from egai.common.canonical import digest
from kvcontinual.governance.fresh_tasks import FreshTaskAuthority
def test_fresh():
 s=Ed25519Signer.generate('k');v=Ed25519Verifier();v.register(s.key_id,s.public_bytes());a=FreshTaskAuthority('a',s,v);c=a.commit_suite('s',digest({'x':1}));assert a.verify_commitment(c);l=a.issue_lease('s',1,'r',digest({'c':1}));assert a.verify_lease(l)
