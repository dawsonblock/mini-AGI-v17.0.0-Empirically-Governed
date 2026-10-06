from kvcontinual.governance.meta_dataset import *

def test_meta_dataset_readiness(tmp_path):
    d=MetaPlasticityDataset(tmp_path/'m.jsonl')
    for i in range(3):d.append(PlasticityOutcome(str(i),'sha256:'+'0'*64,'sha256:'+'1'*64,'skill','sha256:'+'2'*64,i<2,.1,.99,0,1))
    assert d.ready(3,2) and not d.ready(4,2)
