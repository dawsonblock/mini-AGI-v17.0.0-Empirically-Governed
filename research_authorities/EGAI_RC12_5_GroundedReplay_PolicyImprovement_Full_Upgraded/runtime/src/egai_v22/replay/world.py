from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True)
class ReplayNode:
    node_id:str; step:int; observable_state:dict; action:Any; outcome:Any; grounded:bool; parent_id:str|None=None
class PrefixLeakageError(RuntimeError): pass
class GroundedReplayWorld:
    def __init__(self,nodes):
        if any(not n.grounded for n in nodes): raise ValueError('grounded replay accepts grounded nodes only')
        self.nodes={n.node_id:n for n in nodes}
    def observable_prefix(self,step): return tuple(sorted((n for n in self.nodes.values() if n.step<=step),key=lambda n:n.step))
    def outcome(self,node_id,at_step):
        n=self.nodes[node_id]
        if n.step>at_step: raise PrefixLeakageError('future outcome unavailable')
        return n.outcome
class ImaginedReplayWorld:
    def __init__(self,predictor): self.predictor=predictor
    def imagine(self,state,action): return {'outcome_type':'model_predicted','trusted':False,'prediction':self.predictor(state,action)}
