from dataclasses import dataclass
@dataclass(frozen=True)
class CapabilityGapDiagnosis:
    retrieval_failure:bool=False; procedure_failure:bool=False; routing_failure:bool=False; tool_failure:bool=False
    compute_failure:bool=False; composition_failure:bool=False; representation_bottleneck:bool=False
    repeated_verified_count:int=0
    @property
    def genuine_capacity_candidate(self):
        operational = any([self.retrieval_failure,self.procedure_failure,self.routing_failure,self.tool_failure,self.compute_failure,self.composition_failure])
        return self.representation_bottleneck and not operational and self.repeated_verified_count>=25

class CapacityProbe:
    def diagnose(self,**kwargs): return CapabilityGapDiagnosis(**kwargs)
