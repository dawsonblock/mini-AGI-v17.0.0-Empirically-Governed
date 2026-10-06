import pytest
from egai.common.crypto import Ed25519Signer,Ed25519Verifier
from egai.common.canonical import digest
from kvcontinual.governance.fresh_tasks import FreshTaskAuthority,FreshTaskStore

def test_consumption_survives_authority_restart(tmp_path):
    s=Ed25519Signer.generate('k');v=Ed25519Verifier();v.register(s.key_id,s.public_bytes());store=FreshTaskStore(tmp_path/'f.db')
    a=FreshTaskAuthority('a',s,v,store=store);c=a.commit_suite('suite',digest({'tasks':1}));a.issue_lease('suite',c.generation,'runner',digest({'candidate':1}))
    b=FreshTaskAuthority('a',s,v,store=store)
    with pytest.raises(RuntimeError):b.issue_lease('suite',c.generation,'runner2',digest({'candidate':1}))
