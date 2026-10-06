from dataclasses import asdict

from egai.authority.forward_transfer import FrozenTransferEvaluator, TransferPlanRegistrar
from egai.authority.hidden_tasks import HiddenTaskVault
from egai.bench.engine import TaskCase
from egai.bench.forward_transfer import TransferGatePolicy, summarize_transfer
from egai.common.artifacts import ArtifactStore
from egai.common.canonical import digest
from egai.common.crypto import Ed25519Signer, Ed25519Verifier
from egai.common.trust import AuthorityTrust
from egai.cognition.model import FrozenEchoModel
from kvcontinual.governance.fresh_tasks import FreshTaskAuthority, FreshTaskStore


def test_forward_transfer_summary_requires_real_r4_r5_signal():
    pairs={4:([0.0]*6,[1.0]*6),5:([0.0]*6,[1.0]*6)}
    s=summarize_transfer(
        pairs,
        retention_pair=([1.0]*4,[1.0]*4),
        foundation_pair=([1.0]*4,[1.0]*4),
        security_pair=([1.0]*4,[1.0]*4),
        policy=TransferGatePolicy(bootstrap_samples=200),
    )
    assert s.passed
    assert s.forward_transfer == 1.0
    assert s.transfer_breadth == 1.0
    assert all(x.holm_significant for x in s.ring_effects)


def test_missing_required_transfer_ring_fails():
    s=summarize_transfer(
        {4:([0.0]*6,[1.0]*6)},
        retention_pair=([1.0],[1.0]), foundation_pair=([1.0],[1.0]), security_pair=([1.0],[1.0]),
        policy=TransferGatePolicy(bootstrap_samples=100),
    )
    assert not s.passed
    assert not s.gates['required_rings_present']


def _signers():
    benchmark=Ed25519Signer.generate('bench-key')
    evaluator=Ed25519Signer.generate('eval-key')
    verifier=Ed25519Verifier()
    verifier.register(benchmark.key_id,benchmark.public_bytes())
    verifier.register(evaluator.key_id,evaluator.public_bytes())
    trust=AuthorityTrust({'benchmark':(benchmark.key_id,), 'evaluator':(evaluator.key_id,)})
    return benchmark,evaluator,verifier,trust


def _cases():
    out=[]
    for ring in (4,5):
        for i in range(6):
            out.append(TaskCase(f'f{ring}-{i}','future',f'future-{ring}-{i}','OK',task_kind='code',metadata={'transfer_ring':ring}))
    for i in range(3):
        out.append(TaskCase(f'r{i}','retention',f'retain-{i}','OK',metadata={'transfer_ring':0}))
        out.append(TaskCase(f'b{i}','retention',f'foundation-{i}','OK',metadata={'foundation':True,'transfer_ring':0}))
        out.append(TaskCase(f's{i}','security',f'security-{i}','SAFE',metadata={'transfer_ring':0}))
    return out


def test_hidden_task_vault_is_encrypted_and_wrong_key_fails():
    import pytest
    cases=_cases();key=HiddenTaskVault.generate_key();sealed=HiddenTaskVault.seal('suite',1,cases,key)
    blob=str(asdict(sealed))
    assert 'future-4-0' not in blob and 'foundation-0' not in blob
    opened=HiddenTaskVault.open(sealed,key)
    assert len(opened)==len(cases)
    with pytest.raises(Exception):
        HiddenTaskVault.open(sealed,HiddenTaskVault.generate_key())


def test_end_to_end_frozen_transfer_receipt(tmp_path):
    benchmark,evaluator_signer,verifier,trust=_signers()
    store=ArtifactStore(tmp_path/'artifacts')
    fresh=FreshTaskAuthority('fresh',benchmark,verifier,trust,FreshTaskStore(tmp_path/'fresh.db'))
    key=HiddenTaskVault.generate_key();sealed=HiddenTaskVault.seal('suite',1,_cases(),key)
    commitment=fresh.commit_suite('suite',sealed.sealed_digest)
    model=FrozenEchoModel('frozen-test')
    plan=TransferPlanRegistrar('registrar',benchmark).register(
        'plan-1',model.model_digest,digest({'experience':'stream-v1'}),commitment.digest,
        TransferGatePolicy(bootstrap_samples=200),checkpoints=(0,10),
    )
    candidate_digest=digest({'candidate':'skills-v1'})
    lease=fresh.issue_lease('suite',1,'runner',candidate_digest)
    auth=FrozenTransferEvaluator('evaluator',evaluator_signer,verifier,trust,store,fresh)

    def baseline(inp,kind):
        if inp.startswith('future-'): return 'MISS'
        return 'SAFE' if inp.startswith('security-') else 'OK'
    def candidate(inp,kind):
        return 'SAFE' if inp.startswith('security-') else 'OK'
    score=lambda p,e:1.0 if str(p)==str(e) else 0.0
    receipt=auth.evaluate('receipt-1',plan,lease,sealed,key,candidate_digest,model,baseline,candidate,score)
    assert receipt.passed
    assert receipt.model_digest_before==receipt.model_digest_after==model.model_digest
    assert receipt.summary['gates']['required_rings_holm_significant']
    assert auth.verify_receipt(receipt)
    assert store.exists(receipt.raw_result_digest)


def test_model_mutation_blocks_transfer_promotion(tmp_path):
    benchmark,evaluator_signer,verifier,trust=_signers();store=ArtifactStore(tmp_path/'artifacts')
    fresh=FreshTaskAuthority('fresh',benchmark,verifier,trust,FreshTaskStore(tmp_path/'fresh.db'))
    key=HiddenTaskVault.generate_key();sealed=HiddenTaskVault.seal('suite',1,_cases(),key)
    commitment=fresh.commit_suite('suite',sealed.sealed_digest)
    class MutableModel:
        model_digest=digest({'model':'v1'})
    model=MutableModel()
    plan=TransferPlanRegistrar('registrar',benchmark).register('p',model.model_digest,digest({'e':1}),commitment.digest,TransferGatePolicy(bootstrap_samples=100))
    cand=digest({'c':1});lease=fresh.issue_lease('suite',1,'runner',cand)
    def baseline(inp,kind): return 'MISS' if inp.startswith('future-') else ('SAFE' if inp.startswith('security-') else 'OK')
    seen={'n':0}
    def candidate(inp,kind):
        seen['n']+=1
        if seen['n']==1:model.model_digest=digest({'model':'v2'})
        return 'SAFE' if inp.startswith('security-') else 'OK'
    r=FrozenTransferEvaluator('eval',evaluator_signer,verifier,trust,store,fresh).evaluate('r',plan,lease,sealed,key,cand,model,baseline,candidate,lambda p,e:float(p==e))
    assert not r.passed
    assert not r.summary['model_digest_constant']
