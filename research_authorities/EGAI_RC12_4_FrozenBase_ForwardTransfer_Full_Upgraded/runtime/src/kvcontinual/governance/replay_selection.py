from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class ReplayCandidate:
    evidence_id:str; capability_id:str; compatibility:float; threat_probability:float; transfer_value:float; cost:float=1.0
@dataclass(frozen=True)
class ReplaySelection:
    selected:tuple[ReplayCandidate,...]; total_cost:float
class TransferSelectiveReplayPlanner:
    'Chooses replay for threatened and transfer-compatible capabilities, not periodically/randomly.'
    def score(self,c:ReplayCandidate)->float:return max(0.0,c.compatibility)*max(0.0,c.threat_probability)*max(0.0,c.transfer_value)/max(1e-9,c.cost)
    def select(self,candidates:list[ReplayCandidate],budget:float)->ReplaySelection:
        if budget<0: raise ValueError('budget must be non-negative')
        out=[];spent=0.0
        for c in sorted(candidates,key=self.score,reverse=True):
            if c.cost<0: raise ValueError('negative replay cost')
            if spent+c.cost<=budget and self.score(c)>0:out.append(c);spent+=c.cost
        return ReplaySelection(tuple(out),spent)
