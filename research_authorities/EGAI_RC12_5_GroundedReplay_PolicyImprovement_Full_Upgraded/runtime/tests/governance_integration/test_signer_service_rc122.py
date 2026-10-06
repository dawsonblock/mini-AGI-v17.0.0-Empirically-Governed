import os
from egai.common.crypto import Ed25519Signer
from egai.common.canonical import digest
from kvcontinual.governance.signer_service import SignerService,request_signature

def test_socket_permissions_and_replay_rejection(tmp_path):
    p=str(tmp_path/'s.sock');svc=SignerService(p,Ed25519Signer.generate('k')).start()
    try:
        assert (os.stat(p).st_mode & 0o777)==0o600
        d=digest({'x':1});a=request_signature(p,'qualification',d,request_id='r1');b=request_signature(p,'qualification',d,request_id='r1');assert 'signature_b64' in a and b.get('error')=='replayed request'
    finally:svc.close()
