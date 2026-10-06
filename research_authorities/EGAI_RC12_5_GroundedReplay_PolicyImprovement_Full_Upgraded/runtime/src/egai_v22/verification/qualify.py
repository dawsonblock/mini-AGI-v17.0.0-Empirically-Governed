from dataclasses import replace
from egai_v22.core.models import QualificationRecord
from egai_v22.security.signing import ReceiptSigner, ReceiptVerifier
class QualificationPolicy:
    def __init__(self,version='q-v2.1',min_ft=.01,min_breadth=.10,min_learned_ret=.98,min_foundation_ret=.99,max_cal_error=.10,min_prov=1.0,min_ablation=0.0):
        self.version=version; self.min_ft=min_ft; self.min_breadth=min_breadth; self.min_learned_ret=min_learned_ret; self.min_foundation_ret=min_foundation_ret; self.max_cal_error=max_cal_error; self.min_prov=min_prov; self.min_ablation=min_ablation
    def qualify(self,build,evaluation,signer=None):
        reasons=[]
        if evaluation.build_digest!=build.digest(): reasons.append('build_digest_mismatch')
        if evaluation.forward_transfer<self.min_ft: reasons.append('insufficient_forward_transfer')
        if evaluation.transfer_breadth<self.min_breadth: reasons.append('insufficient_transfer_breadth')
        if evaluation.learned_retention<self.min_learned_ret: reasons.append('learned_retention_regression')
        if evaluation.foundation_retention<self.min_foundation_ret: reasons.append('foundation_retention_regression')
        if evaluation.calibration_error>self.max_cal_error: reasons.append('calibration_regression')
        if evaluation.security_regression!=0: reasons.append('security_regression')
        if evaluation.unauthorized_mutation!=0: reasons.append('unauthorized_mutation')
        if evaluation.provenance_closure<self.min_prov: reasons.append('incomplete_provenance')
        if evaluation.ablation_uplift<=self.min_ablation: reasons.append('no_positive_causal_uplift')
        q=QualificationRecord(build.digest(),evaluation.digest(),not reasons,tuple(reasons),self.version)
        if signer:
            q=replace(q,signer_public_key=signer.public_key_b64)
            q=replace(q,signature=signer.sign_obj(q.unsigned()))
        return q
    @staticmethod
    def verify_signature(q): return bool(q.signature) and ReceiptVerifier.verify_obj(q.signer_public_key,q.unsigned(),q.signature)
