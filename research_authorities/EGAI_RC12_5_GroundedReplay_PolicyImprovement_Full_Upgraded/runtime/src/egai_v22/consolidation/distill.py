from dataclasses import dataclass
from egai_v22.core.canonical import sha256_obj

@dataclass(frozen=True)
class DistillationCandidate:
    candidate_id:str
    source_modules:tuple[str,...]
    proposed_target:str
    evidence:tuple[str,...]
    expected_capacity_reduction:float
    expected_transfer_delta:float
    def digest(self): return sha256_obj(self)

class StructuralDistiller:
    """Proposal-only structural compression. Does not modify modules or runtime."""
    def propose(self,candidate_id,source_modules,target,evidence,capacity_reduction,transfer_delta):
        if len(source_modules)<2: raise ValueError('distillation requires multiple sources')
        return DistillationCandidate(candidate_id,tuple(source_modules),target,tuple(evidence),capacity_reduction,transfer_delta)
