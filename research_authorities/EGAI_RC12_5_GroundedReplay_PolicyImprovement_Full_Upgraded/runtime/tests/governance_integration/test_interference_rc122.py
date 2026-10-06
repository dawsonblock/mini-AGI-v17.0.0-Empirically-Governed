from kvcontinual.governance.interference import *

def test_interference_hard_gate():
    e=InterferenceEstimator(0.01,0.02).estimate([CapabilityDelta('old',1,.95),CapabilityDelta('new',.2,.6)])
    assert not e.safe and 'old' in e.affected
