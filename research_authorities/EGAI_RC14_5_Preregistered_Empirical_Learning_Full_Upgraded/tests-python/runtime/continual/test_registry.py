from pathlib import Path
from kvcontinual.continual.registry import AdapterRegistry
from kvcontinual.continual.qualification import QualificationPolicy
from kvcontinual.continual.types import PromotionDecision


def make_candidate(reg, tmp_path, payload: bytes):
    f = tmp_path / (str(len(payload)) + ".safetensors")
    f.write_bytes(payload)
    return reg.register_candidate(str(f), "sha256:base", "sha256:data", {"lr": 1e-5})


def test_promote_and_rollback(tmp_path):
    reg = AdapterRegistry(str(tmp_path / "registry"))
    qpol = QualificationPolicy()
    c1 = make_candidate(reg, tmp_path, b"a")
    q1 = qpol.evaluate(c1.candidate_id, .04, .005, True, True)
    assert q1.decision == PromotionDecision.PROMOTE
    reg.write_qualification(q1)
    reg.promote(c1.candidate_id)

    c2 = make_candidate(reg, tmp_path, b"bb")
    q2 = qpol.evaluate(c2.candidate_id, .05, .005, True, True)
    reg.write_qualification(q2)
    reg.promote(c2.candidate_id)
    assert reg.current_id() == c2.candidate_id
    assert reg.rollback() == c1.candidate_id
