from egai_v22.evidence.admission import EvidenceAdmissionPolicy
from egai_v22.security.capabilities import CapabilityAuthority

class EvidenceAdmissionService:
    """Only this service owns the evidence-append capability."""
    def __init__(self, store, policy=None):
        self.store=store; self.policy=policy or EvidenceAdmissionPolicy()
        self._authority=CapabilityAuthority(); self._cap=self._authority.issue('EVIDENCE_ADMISSION_INTERNAL')
        if hasattr(store,'bind_evidence_capability_authority'):
            store.bind_evidence_capability_authority(self._authority)
    def admit(self, record):
        self.policy.validate(record)
        return self.store.append_evidence(record,_capability=self._cap)
