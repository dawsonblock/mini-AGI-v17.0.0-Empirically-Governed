from kvcontinual.governance.data_plane import GovernanceDataPlane

def test_versioned_state_and_conflict(tmp_path):
    s=GovernanceDataPlane(tmp_path/'g.db')
    a=s.put('belief','b1',{'claim':'x'},expected_version=0)
    b=s.put('belief','b1',{'claim':'y'},expected_version=1)
    assert b.previous_digest==a.value_digest and s.verify_chain('belief','b1')
    try:
        s.put('belief','b1',{'claim':'z'},expected_version=1)
        assert False
    except RuntimeError:
        pass
