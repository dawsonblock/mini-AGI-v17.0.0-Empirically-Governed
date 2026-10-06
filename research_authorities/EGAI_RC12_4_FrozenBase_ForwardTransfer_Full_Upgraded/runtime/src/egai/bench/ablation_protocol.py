from __future__ import annotations
from dataclasses import dataclass

STAGES=(
    "B0_FROZEN",
    "B1_EPISODIC",
    "B2_PROCEDURAL",
    "B3_COMPOSITION",
    "B4_SELECTIVE_REPLAY",
    "B5_ACTIVE_EXPERIMENT",
)

@dataclass(frozen=True)
class AblationResult:
    stage:str
    future_transfer:float
    retention:float
    foundation_retention:float
    security:float
    compute_cost:float
    passed_hard_gates:bool

@dataclass(frozen=True)
class AblationDecision:
    stage:str
    advance:bool
    reason:str


def decide_incremental(previous:AblationResult|None,current:AblationResult,min_increment=.0,max_compute_multiplier=2.0)->AblationDecision:
    if current.stage not in STAGES: raise ValueError('unknown ablation stage')
    if not current.passed_hard_gates:return AblationDecision(current.stage,False,'hard gate failure')
    if previous is None:return AblationDecision(current.stage,True,'baseline established')
    gain=current.future_transfer-previous.future_transfer
    if gain<=min_increment:
        return AblationDecision(current.stage,False,'no incremental held-out forward-transfer gain')
    if previous.compute_cost>0 and current.compute_cost/previous.compute_cost>max_compute_multiplier:
        return AblationDecision(current.stage,False,'compute increase exceeds preregistered limit')
    return AblationDecision(current.stage,True,'incremental transfer gain with hard gates preserved')
