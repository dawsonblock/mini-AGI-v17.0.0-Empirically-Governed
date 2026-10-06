from egai.common.canonical import digest
from egai.common.crypto import Ed25519Signer,Ed25519Verifier
from kvcontinual.governance.rollback import RuntimeState,AtomicRuntimePointer

def state(offset=0):
    ds=[digest({'i':i+offset}) for i in range(8)]
    return RuntimeState(ds[0],ds[1],(ds[2],),ds[3],ds[4],ds[5],ds[6],ds[7])

def test_signed_activation_and_rollback_receipts(tmp_path):
    s=Ed25519Signer.generate('promote'); v=Ed25519Verifier(); v.register(s.key_id,s.public_bytes())
    p=AtomicRuntimePointer(tmp_path/'active.json',signer=s,verifier=v,require_signature=True)
    a=p.activate(state()); assert p.verify_receipt(a) and a.generation==1
    b=p.rollback(state(20)); assert p.verify_receipt(b) and b.generation==2 and b.previous_runtime_digest==a.runtime_digest
    assert (tmp_path/'active.json.receipts.jsonl').exists()
