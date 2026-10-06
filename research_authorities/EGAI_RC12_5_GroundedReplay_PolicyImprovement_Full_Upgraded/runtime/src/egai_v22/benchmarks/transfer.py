from dataclasses import dataclass
RINGS=('R1','R2','R3','R4','R5','R6')
@dataclass(frozen=True)
class TransferVector:
    ring_scores:dict
    retention:float
    calibration_error:float
    provenance_closure:float
    security_regression:int
    experience_count:int
    compute:float=0.0
    capacity_growth:float=0.0
    risk:float=0.0
    @property
    def breadth(self): return sum(1 for r in RINGS if self.ring_scores.get(r,0)>0)/len(RINGS)
    @property
    def forward_transfer(self):
        vals=[self.ring_scores.get(r,0.0) for r in RINGS]
        return sum(vals)/len(vals)
    @property
    def conservative_transfer(self):
        vals=[self.ring_scores.get(r,0.0) for r in RINGS]
        return min(vals) if vals else 0.0
    def constrained_score(self):
        if self.security_regression!=0 or self.provenance_closure<1.0: return float('-inf')
        denom=max(1e-12,self.experience_count+self.compute+self.capacity_growth+self.risk)
        return (self.forward_transfer*self.breadth*self.retention)/denom
