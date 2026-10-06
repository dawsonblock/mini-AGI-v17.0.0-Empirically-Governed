from __future__ import annotations
from dataclasses import dataclass,asdict
from egai.common.canonical import digest
from egai.bench.statistics import paired_bootstrap,EffectEstimate
@dataclass(frozen=True)
class CausalCreditRecord:
    intervention_id:str; baseline_scores:tuple[float,...]; candidate_scores:tuple[float,...]; effect:EffectEstimate; mechanism:str; context_digest:str; record_digest:str=''
class CausalCreditAssigner:
    def assess(self,intervention_id,baseline,candidate,mechanism,context_digest,samples=1000,seed=0):
        e=paired_bootstrap(list(baseline),list(candidate),samples=samples,seed=seed);r=CausalCreditRecord(intervention_id,tuple(baseline),tuple(candidate),e,mechanism,context_digest,'')
        return CausalCreditRecord(**{**asdict(r),'effect':e,'record_digest':digest({k:v for k,v in asdict(r).items() if k!='record_digest'})})
