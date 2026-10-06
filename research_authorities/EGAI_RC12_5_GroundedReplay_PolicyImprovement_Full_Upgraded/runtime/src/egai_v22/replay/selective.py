from dataclasses import dataclass

@dataclass(frozen=True)
class ReplayItem:
    item_id:str
    compatibility:float
    regression_risk:float
    novelty:float
    cost:float=1.0

class TransferSelectiveReplay:
    """Chooses replay for positive transfer and regression defense instead of uniform rehearsal."""
    def score(self,item):
        return (item.compatibility + item.regression_risk + .25*item.novelty) / max(item.cost,1e-12)
    def select(self,items,budget):
        ranked=sorted(items,key=self.score,reverse=True)
        out=[]; used=0.0
        for x in ranked:
            if used+x.cost<=budget:
                out.append(x); used+=x.cost
        return tuple(out)
