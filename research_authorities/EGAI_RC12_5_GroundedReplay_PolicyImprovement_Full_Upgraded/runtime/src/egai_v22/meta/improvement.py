class ImprovementLedger:
    def __init__(self,store): self.store=store
    def record(self,rec):
        if abs(rec.causal_uplift-(rec.observed_forward_transfer-rec.counterfactual_baseline))>1e-9:
            raise ValueError('causal uplift inconsistent with observed-baseline')
        self.store.put_improvement(rec)
