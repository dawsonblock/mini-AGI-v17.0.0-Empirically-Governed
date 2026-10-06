from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timezone
import json

from egai.bench.forward_transfer import TransferGatePolicy, summarize_transfer
from egai.authority.hidden_tasks import HiddenTaskVault, SealedTaskSuite
from egai.common.canonical import digest
from egai.common.crypto import SignedEnvelope
from kvcontinual.governance.transfer_rings import TransferRing


@dataclass(frozen=True)
class FrozenTransferPlan:
    plan_id: str
    version: str
    base_model_digest: str
    experience_digest: str
    hidden_suite_commitment_digest: str
    checkpoints: tuple[int,...]
    ablation_stages: tuple[str,...]
    policy: dict
    created_at: str
    registrar_id: str
    key_id: str=''
    signature_b64: str=''

    @property
    def digest(self):
        return digest(asdict(replace(self,key_id='',signature_b64='')))


@dataclass(frozen=True)
class ForwardTransferReceipt:
    receipt_id: str
    plan_digest: str
    candidate_digest: str
    lease_id: str
    sealed_suite_digest: str
    model_digest_before: str
    model_digest_after: str
    raw_result_digest: str
    summary: dict
    passed: bool
    evaluator_id: str
    created_at: str
    key_id: str=''
    signature_b64: str=''

    @property
    def digest(self):
        return digest(asdict(replace(self,key_id='',signature_b64='')))


class TransferPlanRegistrar:
    def __init__(self,registrar_id,signer):
        self.registrar_id=registrar_id; self.signer=signer

    def register(self, plan_id, base_model_digest, experience_digest, hidden_suite_commitment_digest,
                 policy:TransferGatePolicy, checkpoints=(0,50,100,250,500,1000),
                 ablation_stages=("B0_FROZEN","B1_EPISODIC","B2_PROCEDURAL","B3_COMPOSITION","B4_SELECTIVE_REPLAY","B5_ACTIVE_EXPERIMENT")):
        u=FrozenTransferPlan(plan_id,"rc12.4-v1",base_model_digest,experience_digest,hidden_suite_commitment_digest,
                             tuple(checkpoints),tuple(ablation_stages),asdict(policy),datetime.now(timezone.utc).isoformat(),self.registrar_id)
        env=self.signer.sign(asdict(u))
        return replace(u,key_id=env.key_id,signature_b64=env.signature_b64)


class FrozenTransferEvaluator:
    """Independent hidden-suite evaluator for a frozen base model.

    The evaluator verifies a one-time FreshTaskAuthority lease, decrypts the hidden suite only
    inside the evaluator boundary, evaluates paired baseline/candidate behavior, checks the base
    model digest before and after, stores raw paired outcomes in the artifact store, and returns
    only a signed aggregate receipt.
    """
    def __init__(self,evaluator_id,signer,verifier,trust,artifact_store,fresh_task_authority):
        self.evaluator_id=evaluator_id;self.signer=signer;self.verifier=verifier;self.trust=trust
        self.artifacts=artifact_store;self.fresh=fresh_task_authority

    def verify_plan(self,plan:FrozenTransferPlan):
        self.trust.require('benchmark',plan.key_id)
        return self.verifier.verify(asdict(replace(plan,key_id='',signature_b64='')),SignedEnvelope(plan.key_id,plan.signature_b64))

    def evaluate(self,receipt_id,plan:FrozenTransferPlan,lease,sealed:SealedTaskSuite,vault_key:bytes,
                 candidate_digest:str,frozen_model,baseline_solver,candidate_solver,scorer):
        if not self.verify_plan(plan): raise PermissionError('invalid transfer plan signature')
        if not self.fresh.verify_lease(lease): raise PermissionError('invalid fresh-task lease')
        if lease.candidate_digest != candidate_digest: raise PermissionError('lease candidate mismatch')
        commitment=self.fresh._commitment(lease.suite_id,lease.generation)
        if commitment is None or commitment.digest != lease.commitment_digest: raise PermissionError('fresh-task commitment mismatch')
        if sealed.suite_id!=lease.suite_id or sealed.generation!=lease.generation: raise PermissionError('sealed suite generation mismatch')
        if sealed.sealed_digest!=commitment.sealed_suite_digest: raise PermissionError('sealed suite digest mismatch')
        if plan.hidden_suite_commitment_digest!=commitment.digest: raise PermissionError('plan/hidden-suite commitment mismatch')
        before=frozen_model.model_digest
        if before!=plan.base_model_digest: raise RuntimeError('base model identity does not match preregistration')
        cases=HiddenTaskVault.open(sealed,vault_key)
        ring_pairs={};ret=([],[]);foundation=([],[]);security=([],[]);raw=[]
        for c in cases:
            b=baseline_solver(c.input,c.task_kind); a=candidate_solver(c.input,c.task_kind)
            b=b.text if hasattr(b,'text') else b; a=a.text if hasattr(a,'text') else a
            bs=float(scorer(b,c.expected)); cs=float(scorer(a,c.expected))
            ring=int(c.metadata.get('transfer_ring',0))
            if c.split=='future':
                if ring not in {int(x) for x in TransferRing}: raise ValueError('future case missing valid transfer_ring')
                rb,rc=ring_pairs.setdefault(ring,([],[]));rb.append(bs);rc.append(cs)
            elif c.split=='security':
                security[0].append(bs);security[1].append(cs)
            elif c.split=='retention':
                target=foundation if c.metadata.get('foundation',False) else ret
                target[0].append(bs);target[1].append(cs)
            else: raise ValueError('hidden evaluation split must be future/retention/security')
            raw.append({'case_id':c.case_id,'split':c.split,'ring':ring,'baseline_score':bs,'candidate_score':cs})
        if not all((ret[0],foundation[0],security[0])): raise ValueError('retention, foundation, and security cases are required')
        policy=TransferGatePolicy(**plan.policy)
        summary=summarize_transfer(ring_pairs,retention_pair=ret,foundation_pair=foundation,security_pair=security,policy=policy)
        after=frozen_model.model_digest
        frozen=(before==after==plan.base_model_digest)
        d=self.artifacts.put_bytes(json.dumps(raw,sort_keys=True,separators=(',',':')).encode())
        summary_dict=summary.as_dict();summary_dict['model_digest_constant']=frozen
        passed=bool(summary.passed and frozen)
        u=ForwardTransferReceipt(receipt_id,plan.digest,candidate_digest,lease.lease_id,sealed.sealed_digest,before,after,d,summary_dict,passed,self.evaluator_id,datetime.now(timezone.utc).isoformat())
        env=self.signer.sign(asdict(u));return replace(u,key_id=env.key_id,signature_b64=env.signature_b64)

    def verify_receipt(self,receipt:ForwardTransferReceipt):
        self.trust.require('evaluator',receipt.key_id)
        return self.verifier.verify(asdict(replace(receipt,key_id='',signature_b64='')),SignedEnvelope(receipt.key_id,receipt.signature_b64))
