from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import json
from egai.common.canonical import digest
@dataclass(frozen=True)
class PlasticityOutcome:
    record_id:str; context_digest:str; proposal_digest:str; mechanism:str; qualification_digest:str; promoted:bool; future_transfer:float; retention:float; interference:float; cost:float; record_digest:str=''
class MetaPlasticityDataset:
    'Collects independently qualified causal records. It does not train a meta-learner.'
    def __init__(self,path:str|Path):self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.path.touch(exist_ok=True)
    def append(self,r:PlasticityOutcome):
        raw={k:v for k,v in asdict(r).items() if k!='record_digest'};sealed=PlasticityOutcome(**raw,record_digest=digest(raw))
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(asdict(sealed),sort_keys=True,separators=(',',':'))+'\n')
        return sealed
    def load(self):
        out=[]
        with self.path.open() as f:
            for line in f:
                if line.strip():out.append(PlasticityOutcome(**json.loads(line)))
        return out
    def ready(self,min_records:int=1000,min_promoted:int=100):
        rows=self.load();return len(rows)>=min_records and sum(r.promoted for r in rows)>=min_promoted
