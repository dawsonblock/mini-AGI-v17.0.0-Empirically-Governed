from __future__ import annotations
from dataclasses import dataclass
import math
@dataclass(frozen=True)
class CapabilityDelta:
    capability_id:str; baseline:float; candidate:float; importance:float=1.0
    @property
    def delta(self): return self.candidate-self.baseline
@dataclass(frozen=True)
class InterferenceEstimate:
    weighted_regression:float; worst_regression:float; affected:tuple[str,...]; safe:bool
class InterferenceEstimator:
    def __init__(self,max_weighted_regression:float=0.0,max_single_regression:float=0.0): self.max_weighted_regression=max_weighted_regression;self.max_single_regression=max_single_regression
    def estimate(self,deltas:list[CapabilityDelta])->InterferenceEstimate:
        if not deltas:return InterferenceEstimate(0.0,0.0,(),True)
        neg=[d for d in deltas if d.delta<0];total=sum(max(0,d.importance) for d in deltas) or 1.0
        wr=sum(max(0,d.importance)*max(0,-d.delta) for d in deltas)/total;worst=max((max(0,-d.delta) for d in deltas),default=0.0)
        return InterferenceEstimate(wr,worst,tuple(d.capability_id for d in neg),wr<=self.max_weighted_regression and worst<=self.max_single_regression)
def cosine_interference(update_a:list[float],update_b:list[float])->float:
    if len(update_a)!=len(update_b) or not update_a: raise ValueError('equal non-empty vectors required')
    na=math.sqrt(sum(x*x for x in update_a));nb=math.sqrt(sum(x*x for x in update_b))
    if na==0 or nb==0:return 0.0
    return -sum(a*b for a,b in zip(update_a,update_b))/(na*nb)
