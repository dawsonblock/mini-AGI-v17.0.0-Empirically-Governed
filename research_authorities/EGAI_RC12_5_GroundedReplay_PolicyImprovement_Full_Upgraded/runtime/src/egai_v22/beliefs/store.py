from dataclasses import replace
from egai_v22.core.models import Belief

class BeliefStore:
    """Versioned derived view; beliefs may change but evidence references remain."""
    def __init__(self): self._versions={}
    def create(self,b:Belief):
        if b.belief_id in self._versions: raise ValueError('belief exists')
        self._versions[b.belief_id]=[b]; return b
    def revise(self,belief_id,*,claim=None,confidence=None,supporting_evidence=None,contradicting_evidence=None,status=None):
        old=self._versions[belief_id][-1]
        new=replace(old,
            claim=old.claim if claim is None else claim,
            confidence=old.confidence if confidence is None else confidence,
            supporting_evidence=list(old.supporting_evidence if supporting_evidence is None else supporting_evidence),
            contradicting_evidence=list(old.contradicting_evidence if contradicting_evidence is None else contradicting_evidence),
            status=old.status if status is None else status)
        self._versions[belief_id].append(new); return new
    def current(self,belief_id): return self._versions[belief_id][-1]
    def history(self,belief_id): return tuple(self._versions[belief_id])
