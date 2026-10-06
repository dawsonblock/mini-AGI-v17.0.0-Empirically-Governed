from dataclasses import dataclass
from egai_v22.core.canonical import sha256_obj

@dataclass(frozen=True)
class EvidenceCandidate:
    candidate_id: str
    record: object
    submitted_by: str
    reason: str = ''
    def digest(self): return sha256_obj({'candidate_id':self.candidate_id,'record':self.record,'submitted_by':self.submitted_by,'reason':self.reason})

class EvidenceQuarantine:
    def __init__(self): self._candidates={}
    def submit(self,candidate):
        if candidate.candidate_id in self._candidates: raise ValueError('duplicate evidence candidate')
        self._candidates[candidate.candidate_id]=candidate
        return candidate.digest()
    def pop(self,candidate_id): return self._candidates.pop(candidate_id)
    def get(self,candidate_id): return self._candidates[candidate_id]
    def ids(self): return tuple(self._candidates)
