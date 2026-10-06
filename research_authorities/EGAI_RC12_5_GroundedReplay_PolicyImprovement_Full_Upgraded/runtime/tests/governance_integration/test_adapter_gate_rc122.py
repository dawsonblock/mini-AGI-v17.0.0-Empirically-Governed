from kvcontinual.governance.adapter_gate import *

def test_adapter_requires_cheaper_layers_exhausted():
    g=AdapterEscalationGate();e=AdapterEvidence(100,30,True,True,False,True,.2,.01,True);assert not g.decide(e).allow
    e=AdapterEvidence(100,30,True,True,True,True,.2,.01,True);assert g.decide(e).allow
