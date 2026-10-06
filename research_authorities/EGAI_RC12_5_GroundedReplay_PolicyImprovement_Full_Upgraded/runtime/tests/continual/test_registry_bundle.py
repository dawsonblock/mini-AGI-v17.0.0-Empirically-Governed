from kvcontinual.continual.registry import AdapterRegistry
from kvcontinual.continual.qualification import QualificationPolicy


def test_directory_adapter_is_digest_bound(tmp_path):
    bundle = tmp_path / "mlx-adapter"
    bundle.mkdir()
    (bundle / "adapters.safetensors").write_bytes(b"weights")
    (bundle / "adapter_config.json").write_text('{"rank":8}')
    reg = AdapterRegistry(str(tmp_path / "reg"))
    m = reg.register_candidate(str(bundle), "sha256:base", "sha256:data", {"lr": 1e-5})
    assert m.adapter_kind == "directory"
    q = QualificationPolicy().evaluate(m.candidate_id, 0.04, 0.0, True, True)
    reg.write_qualification(q)
    reg.promote(m.candidate_id)
    assert reg.current_id() == m.candidate_id


def test_directory_mutation_after_qualification_is_rejected(tmp_path):
    bundle = tmp_path / "mlx-adapter"
    bundle.mkdir()
    weights = bundle / "adapters.safetensors"
    weights.write_bytes(b"good")
    reg = AdapterRegistry(str(tmp_path / "reg"))
    m = reg.register_candidate(str(bundle), "sha256:base", "sha256:data", {})
    q = QualificationPolicy().evaluate(m.candidate_id, 0.04, 0.0, True, True)
    reg.write_qualification(q)
    candidate_weights = reg.candidates / m.candidate_id / bundle.name / "adapters.safetensors"
    candidate_weights.write_bytes(b"mutated")
    try:
        reg.promote(m.candidate_id)
    except RuntimeError as e:
        assert "digest mismatch" in str(e)
    else:
        raise AssertionError("mutated bundle was promoted")
