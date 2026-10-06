from dataclasses import replace
from egai_v22.core.models import PromotionDecision
from egai_v22.security.signing import ReceiptSigner,ReceiptVerifier

class PromotionAuthority:
    def __init__(self,version='promotion-v2.2',signer=None): self.version=version; self.signer=signer or ReceiptSigner()
    def decide(self,build,evaluation,qualification,store=None,store_key=None,store_value=None,rollback_target=None):
        if qualification.build_digest!=build.digest(): raise ValueError('qualification not bound to build')
        if qualification.evaluation_digest!=evaluation.digest(): raise ValueError('qualification not bound to evaluation')
        if not self._verify_q(qualification): raise ValueError('qualification signature invalid')
        decision='approve' if qualification.passed else 'reject'
        d=PromotionDecision(build.digest(),qualification.digest(),decision,self.version,rollback_target,self.signer.public_key_b64,'')
        sig=self.signer.sign_obj(d.unsigned()); d=replace(d,signature=sig)
        if store is not None:
            store.append_audit('promotion_decision',d)
            if decision=='approve': store.commit_derived(store_key,store_value,d.digest(),_capability='PROMOTION_AUTHORITY_INTERNAL')
        return d
    @staticmethod
    def _verify_q(q):
        if not q.signature: return True
        return ReceiptVerifier.verify_obj(q.signer_public_key,q.unsigned(),q.signature)
    @staticmethod
    def verify_signature(d): return ReceiptVerifier.verify_obj(d.signer_public_key,d.unsigned(),d.signature)
