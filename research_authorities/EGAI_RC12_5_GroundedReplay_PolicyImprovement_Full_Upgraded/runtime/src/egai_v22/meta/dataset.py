from dataclasses import dataclass

@dataclass(frozen=True)
class MetaLearningExample:
    state_digest:str
    action:str
    predicted_reward:float
    observed_reward:float
    counterfactual_baseline:float
    qualification_passed:bool

class ImprovementDataset:
    def __init__(self,min_records=1000): self.min_records=min_records; self._rows=[]
    def add(self,row): self._rows.append(row)
    @property
    def ready(self): return len(self._rows)>=self.min_records
    def rows(self): return tuple(self._rows)
