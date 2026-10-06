from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class AdapterEvidence:
    verified_gap_count:int; independent_tasks:int; retrieval_failed:bool; procedure_failed:bool; composition_failed:bool; representation_bottleneck:bool; expected_forward_transfer:float; expected_interference:float; frozen_base_verified:bool
@dataclass(frozen=True)
class GateDecision:
    allow:bool; reasons:tuple[str,...]
class AdapterEscalationGate:
    def __init__(self,min_verified_gaps=50,min_independent_tasks=20,min_margin=0.02):self.min_verified_gaps=min_verified_gaps;self.min_independent_tasks=min_independent_tasks;self.min_margin=min_margin
    def decide(self,e:AdapterEvidence)->GateDecision:
        reasons=[]
        if not e.frozen_base_verified:reasons.append('base model not verified frozen')
        if e.verified_gap_count<self.min_verified_gaps:reasons.append('insufficient repeated verified gaps')
        if e.independent_tasks<self.min_independent_tasks:reasons.append('insufficient task diversity')
        if not (e.retrieval_failed and e.procedure_failed and e.composition_failed):reasons.append('cheaper mechanisms not exhausted')
        if not e.representation_bottleneck:reasons.append('representation bottleneck not demonstrated')
        if e.expected_forward_transfer-e.expected_interference<self.min_margin:reasons.append('transfer margin too small')
        return GateDecision(not reasons,tuple(reasons))
