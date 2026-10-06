from dataclasses import dataclass
@dataclass(frozen=True)
class ReplayObjective:
    beta_cost:float=0.01
    beta_parallelism:float=0.0
    def score(self,best_quality,attempts,rounds):
        par=(attempts/max(1,rounds)) if attempts else 0.0
        return float(best_quality)-self.beta_cost*attempts+self.beta_parallelism*par
