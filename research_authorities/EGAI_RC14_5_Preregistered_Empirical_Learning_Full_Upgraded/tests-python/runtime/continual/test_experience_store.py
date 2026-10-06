from kvcontinual.continual.experience import Episode
from kvcontinual.continual.experience_store import ExperienceStore
from kvcontinual.continual.dataset_export import export_mlx_dataset


def test_experience_persistence_and_export(tmp_path):
    db = tmp_path / "exp.sqlite3"
    store = ExperienceStore(str(db))
    e = Episode(prompt="new fact?", response="answer")
    store.append(e, importance=0.9)
    assert store.list_training_ready() == []
    store.mark_verified(e.id, importance=0.9)
    ready = store.list_training_ready()
    assert len(ready) == 1 and ready[0].id == e.id
    train, digest, ids = export_mlx_dataset(store, str(tmp_path / "data"))
    assert train.is_file()
    assert digest.startswith("sha256:")
    assert ids == [e.id]
    assert store.list_training_ready() == []
    reopened = ExperienceStore(str(db))
    assert reopened.conn.execute("select count(*) from episodes").fetchone()[0] == 1
