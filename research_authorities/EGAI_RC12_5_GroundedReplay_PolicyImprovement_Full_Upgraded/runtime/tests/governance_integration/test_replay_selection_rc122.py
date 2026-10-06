from kvcontinual.governance.replay_selection import *

def test_selects_threat_and_transfer_compatible_items():
    p=TransferSelectiveReplayPlanner();xs=[ReplayCandidate('a','c1',1,.9,1,1),ReplayCandidate('b','c2',.1,.1,.1,1)]
    r=p.select(xs,1);assert [x.evidence_id for x in r.selected]==['a']
