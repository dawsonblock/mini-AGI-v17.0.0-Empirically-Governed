import json
from kvcontinual.continual.experience import Episode
from kvcontinual.continual.experience_store import ExperienceStore
from kvcontinual.continual.dataset_export import export_mlx_dataset
from kvcontinual.continual.registry import AdapterRegistry
from kvcontinual.continual.qualification import QualificationPolicy


def test_end_to_end_candidate_lifecycle(tmp_path):
    store = ExperienceStore(str(tmp_path / "exp.sqlite3"))
    e = Episode(prompt="p", response="r")
    store.append(e)
    store.mark_verified(e.id)
    train, dataset_digest, ids = export_mlx_dataset(store, str(tmp_path / "data"))
    run = store.create_learning_run(dataset_digest, len(ids), {"train": str(train)})

    adapter = tmp_path / "adapter.safetensors"
    adapter.write_bytes(b"adapter-v1")
    reg = AdapterRegistry(str(tmp_path / "registry"))
    m = reg.register_candidate(str(adapter), "sha256:base", dataset_digest, {"lr": 1e-5})
    store.bind_candidate(run, m.candidate_id)

    q = QualificationPolicy().evaluate(m.candidate_id, 0.05, 0.0, True, True)
    q.evaluation_digest = "sha256:eval"
    q.evaluator_digest = "sha256:evaluator"
    reg.write_qualification(q)
    dst = reg.promote(m.candidate_id)
    assert dst.is_dir()
    assert reg.current_id() == m.candidate_id
