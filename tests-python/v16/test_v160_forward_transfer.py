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


def _signers():
    benchmark=Ed25519Signer.generate('bench-key')
    evaluator=Ed25519Signer.generate('eval-key')
    verifier=Ed25519Verifier(); verifier.register(benchmark.key_id,benchmark.public_bytes()); verifier.register(evaluator.key_id,evaluator.public_bytes())
    trust=AuthorityTrust({'benchmark':(benchmark.key_id,), 'evaluator':(evaluator.key_id,)})
    return benchmark,evaluator,verifier,trust


def _cases():
    out=[]
    for ring in (4,5):
        for i in range(6): out.append(TaskCase(f'f{ring}-{i}','future',f'future-{ring}-{i}','OK',task_kind='code',metadata={'transfer_ring':ring}))
    for i in range(3):
        out.append(TaskCase(f'r{i}','retention',f'retain-{i}','OK',metadata={'transfer_ring':0}))
        out.append(TaskCase(f'b{i}','retention',f'foundation-{i}','OK',metadata={'foundation':True,'transfer_ring':0}))
        out.append(TaskCase(f's{i}','security',f'security-{i}','SAFE',metadata={'transfer_ring':0}))
    return out


def test_rc124_hidden_forward_transfer_runs_inside_v16_trunk(tmp_path):
    benchmark,evaluator_signer,verifier,trust=_signers()
    store=ArtifactStore(tmp_path/'artifacts')
    fresh=FreshTaskAuthority('fresh',benchmark,verifier,trust,FreshTaskStore(tmp_path/'fresh.db'))
    key=HiddenTaskVault.generate_key(); sealed=HiddenTaskVault.seal('suite',1,_cases(),key)
    commitment=fresh.commit_suite('suite',sealed.sealed_digest)
    model=FrozenEchoModel('frozen-test')
    plan=TransferPlanRegistrar('registrar',benchmark).register(
        'plan-1',model.model_digest,digest({'experience':'stream-v1'}),commitment.digest,
        TransferGatePolicy(bootstrap_samples=200),checkpoints=(0,10),
    )
    candidate_digest=digest({'candidate':'skills-v1'}); lease=fresh.issue_lease('suite',1,'runner',candidate_digest)
    auth=FrozenTransferEvaluator('evaluator',evaluator_signer,verifier,trust,store,fresh)
    def baseline(inp,kind): return 'MISS' if inp.startswith('future-') else ('SAFE' if inp.startswith('security-') else 'OK')
    def candidate(inp,kind): return 'SAFE' if inp.startswith('security-') else 'OK'
    receipt=auth.evaluate('receipt-1',plan,lease,sealed,key,candidate_digest,model,baseline,candidate,lambda p,e:float(p==e))
    assert receipt.passed and auth.verify_receipt(receipt)
    assert receipt.summary['gates']['required_rings_holm_significant']
    assert receipt.model_digest_before == receipt.model_digest_after
