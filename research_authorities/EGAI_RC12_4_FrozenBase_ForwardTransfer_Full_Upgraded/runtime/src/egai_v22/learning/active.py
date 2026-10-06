from dataclasses import dataclass

@dataclass(frozen=True)
class ExperimentCandidate:
    experiment_id:str
    expected_information_gain:float
    cost:float
    risk:float
    hypothesis_ids:tuple[str,...]=()

class ActiveExperimentPlanner:
    """Ranks experiments by expected information gain per cost+risk; execution remains external."""
    def rank(self,candidates):
        def score(c): return c.expected_information_gain / max(1e-12,c.cost+c.risk)
        return sorted(candidates,key=score,reverse=True)
    def choose(self,candidates,max_risk=1.0):
        feasible=[c for c in candidates if c.risk<=max_risk]
        if not feasible: return None
        return self.rank(feasible)[0]
