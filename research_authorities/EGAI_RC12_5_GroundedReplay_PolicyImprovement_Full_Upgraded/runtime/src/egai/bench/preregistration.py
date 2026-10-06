from __future__ import annotations
from dataclasses import dataclass,asdict,replace
from datetime import datetime,timezone
from egai.common.canonical import digest
from egai.common.crypto import SignedEnvelope

@dataclass(frozen=True)
class ExperimentPreregistration:
    experiment_id:str
    hypothesis:str
    base_model_digest:str
    experience_stream_digest:str
    hidden_suite_commitment_digest:str
    primary_metric:str
    checkpoints:tuple[int,...]
    stop_conditions:tuple[str,...]
    alpha:float
    created_at:str
    registrar_id:str
    key_id:str=''
    signature_b64:str=''
    @property
    def digest(self):return digest(asdict(replace(self,key_id='',signature_b64='')))

class PreregistrationAuthority:
    def __init__(self,registrar_id,signer,verifier,trust):self.registrar_id=registrar_id;self.signer=signer;self.verifier=verifier;self.trust=trust
    def create(self,experiment_id,hypothesis,base_model_digest,experience_stream_digest,hidden_suite_commitment_digest,checkpoints=(0,50,100,250,500,1000),alpha=.05):
        if not hypothesis.strip():raise ValueError('hypothesis required')
        if not 0<alpha<1:raise ValueError('alpha must be in (0,1)')
        u=ExperimentPreregistration(experiment_id,hypothesis,base_model_digest,experience_stream_digest,hidden_suite_commitment_digest,'R4_R5_forward_transfer',tuple(checkpoints),('base_model_digest_changed','security_regression','foundation_retention_below_gate'),alpha,datetime.now(timezone.utc).isoformat(),self.registrar_id)
        e=self.signer.sign(asdict(u));return replace(u,key_id=e.key_id,signature_b64=e.signature_b64)
    def verify(self,p):
        self.trust.require('benchmark',p.key_id)
        return self.verifier.verify(asdict(replace(p,key_id='',signature_b64='')),SignedEnvelope(p.key_id,p.signature_b64))
