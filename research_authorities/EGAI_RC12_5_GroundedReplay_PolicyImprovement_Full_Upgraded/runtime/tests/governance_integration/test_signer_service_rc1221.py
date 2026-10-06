import time
from egai.common.crypto import Ed25519Signer
from egai.common.canonical import digest
from kvcontinual.governance.signer_service import SignerService,request_signature

def test_replay_survives_service_restart_and_purpose_is_scoped(tmp_path):
    sock=str(tmp_path/'qual.sock'); db=tmp_path/'replay.db'; signer=Ed25519Signer.generate('q')
    d=digest({'x':1}); rid='r'*32
    a=SignerService(sock,signer,replay_store_path=db,allowed_purposes={'qualification'},authority_id='qualifier').start()
    try:
        ok=request_signature(sock,'qualification',d,request_id=rid)
        assert 'signature_b64' in ok and ok['authority_id']=='qualifier'
        assert request_signature(sock,'promotion',d).get('error')=='purpose denied'
    finally:
        a.close()
    b=SignerService(sock,signer,replay_store_path=db,allowed_purposes={'qualification'},authority_id='qualifier').start()
    try:
        assert request_signature(sock,'qualification',d,request_id=rid).get('error')=='replayed request'
    finally:
        b.close()

def test_stale_request_is_rejected(tmp_path):
    sock=str(tmp_path/'s.sock'); svc=SignerService(sock,Ed25519Signer.generate('k'),max_age_s=.01).start()
    try:
        r=request_signature(sock,'qualification',digest({'x':1}),request_id='a'*32,ts_ns=time.time_ns()-10**9)
        assert r.get('error')=='stale or future request'
    finally:
        svc.close()
