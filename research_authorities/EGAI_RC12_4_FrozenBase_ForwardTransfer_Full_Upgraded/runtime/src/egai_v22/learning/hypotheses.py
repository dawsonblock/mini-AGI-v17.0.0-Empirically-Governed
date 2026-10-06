from egai_v22.core.models import Hypothesis
class HypothesisRegistry:
    def __init__(self): self._x={}
    def add(self,h):
        if h.hypothesis_id in self._x: raise ValueError('duplicate hypothesis')
        self._x[h.hypothesis_id]=h
    def support(self,hid,eid,gain=.08):
        h=self._x[hid]; h.evidence_for.append(eid); h.confidence=min(1,h.confidence+gain)
    def contradict(self,hid,eid,penalty=.15):
        h=self._x[hid]; h.evidence_against.append(eid); h.confidence=max(0,h.confidence-penalty)
        if h.confidence<.2: h.status='falsified'
    def get(self,hid): return self._x[hid]
