from kvcontinual.execution.durability.control_state import ControlState


def test_global_control_sequence_and_checkpoint(tmp_path):
    c = ControlState(tmp_path / "control.sqlite3")
    assert c.reserve(transaction_id="p1", kind="promotion", expected_generation=1) == 1
    assert c.reserve(transaction_id="r1", kind="rollback", expected_generation=0) == 2
    c.update_phase("p1", "committed")
    r = c.record("p1")
    assert r is not None
    c.checkpoint(r)
    assert c.checkpoint_state()["last_sequence"] == 1
    ok, detail = c.integrity_check()
    assert ok, detail
