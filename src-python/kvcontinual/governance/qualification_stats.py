from __future__ import annotations
from dataclasses import dataclass
from egai.bench.statistics import paired_bootstrap,EffectEstimate
@dataclass(frozen=True)
class StatisticalDecision:
    passed:bool; reason:str; effect:EffectEstimate; alpha:float; min_effect:float
def alpha_spending_alpha(look:int,total_looks:int,overall_alpha:float=.05)->float:
    if look<1 or total_looks<1 or look>total_looks: raise ValueError('invalid look')
    return overall_alpha/total_looks
def qualify_paired(baseline,candidate,*,min_effect:float=0.0,look:int=1,total_looks:int=1,overall_alpha:float=.05,samples:int=2000,seed:int=0)->StatisticalDecision:
    alpha=alpha_spending_alpha(look,total_looks,overall_alpha);e=paired_bootstrap(list(baseline),list(candidate),samples=samples,seed=seed,alpha=alpha);ok=e.mean_gain>=min_effect and e.ci_low>0
    return StatisticalDecision(ok,'positive preregistered effect' if ok else 'effect/CI gate failed',e,alpha,min_effect)
