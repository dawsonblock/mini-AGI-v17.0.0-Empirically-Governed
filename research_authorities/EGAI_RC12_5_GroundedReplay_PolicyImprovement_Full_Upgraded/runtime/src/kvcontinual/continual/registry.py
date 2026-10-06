from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from kvcontinual.continual.digests import sha256_json, sha256_path
from kvcontinual.continual.types import QualificationRecord, PromotionDecision

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass
class CandidateManifest:
    candidate_id: str
    base_model_digest: str
    parent_adapter_digest: str | None
    dataset_digest: str
    training_config_digest: str
    adapter_digest: str
    adapter_filename: str
    adapter_kind: str
    created_at: str


class AdapterRegistry:
    """Digest-bound candidate/promotion registry.

    Candidate bytes are re-hashed both when qualification is recorded and again
    immediately before promotion. Metadata writes use atomic rename. Candidate
    identifiers are namespace-safe and cannot escape the registry root.
    """

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.candidates = self.root / "candidates"
        self.promoted = self.root / "promoted"
        self.meta = self.root / "meta"
        for p in (self.candidates, self.promoted, self.meta):
            p.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_id(candidate_id: str) -> str:
        if not _ID_RE.fullmatch(candidate_id) or candidate_id in {".", ".."}:
            raise ValueError("invalid candidate_id")
        return candidate_id

    def _candidate_dir(self, candidate_id: str) -> Path:
        candidate_id = self._validate_id(candidate_id)
        p = (self.candidates / candidate_id).resolve()
        if p.parent != self.candidates:
            raise ValueError("candidate path escapes registry")
        return p

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    def register_candidate(self, adapter_file: str, base_model_digest: str, dataset_digest: str, training_config: dict, parent_adapter_digest: str | None = None) -> CandidateManifest:
        cid = str(uuid.uuid4())
        dst_dir = self._candidate_dir(cid)
        dst_dir.mkdir()
        src = Path(adapter_file)
        if not src.exists():
            raise FileNotFoundError(adapter_file)
        if not (src.is_file() or src.is_dir()):
            raise ValueError("adapter artifact must be a file or directory")
        dst = dst_dir / src.name
        adapter_kind = "directory" if src.is_dir() else "file"
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        manifest = CandidateManifest(
            candidate_id=cid,
            base_model_digest=base_model_digest,
            parent_adapter_digest=parent_adapter_digest,
            dataset_digest=dataset_digest,
            training_config_digest=sha256_json(training_config),
            adapter_digest=sha256_path(dst),
            adapter_filename=dst.name,
            adapter_kind=adapter_kind,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._atomic_json(dst_dir / "manifest.json", asdict(manifest))
        return manifest

    def _load_manifest(self, candidate_id: str) -> tuple[Path, dict]:
        cdir = self._candidate_dir(candidate_id)
        mpath = cdir / "manifest.json"
        if not mpath.is_file():
            raise FileNotFoundError("candidate manifest not found")
        manifest = json.loads(mpath.read_text())
        if manifest.get("candidate_id") != candidate_id:
            raise RuntimeError("candidate manifest identity mismatch")
        return cdir, manifest

    def _verify_candidate_bytes(self, candidate_id: str) -> tuple[Path, dict, str, str]:
        cdir, manifest = self._load_manifest(candidate_id)
        name = manifest.get("adapter_filename")
        if not isinstance(name, str) or Path(name).name != name:
            raise RuntimeError("invalid adapter filename in manifest")
        adapter = cdir / name
        kind = manifest.get("adapter_kind", "file")
        if kind == "file" and not adapter.is_file():
            raise RuntimeError("candidate adapter file missing")
        if kind == "directory" and not adapter.is_dir():
            raise RuntimeError("candidate adapter directory missing")
        if kind not in {"file", "directory"}:
            raise RuntimeError("invalid adapter kind")
        adapter_digest = sha256_path(adapter)
        if adapter_digest != manifest.get("adapter_digest"):
            raise RuntimeError("candidate adapter digest mismatch")
        manifest_digest = sha256_json(manifest)
        return cdir, manifest, adapter_digest, manifest_digest

    def write_qualification(self, q: QualificationRecord) -> None:
        cdir, _manifest, adapter_digest, manifest_digest = self._verify_candidate_bytes(q.candidate_id)
        if q.adapter_digest and q.adapter_digest != adapter_digest:
            raise RuntimeError("qualification adapter digest does not match candidate")
        if q.candidate_manifest_digest and q.candidate_manifest_digest != manifest_digest:
            raise RuntimeError("qualification manifest digest does not match candidate")
        q.adapter_digest = adapter_digest
        q.candidate_manifest_digest = manifest_digest
        payload = asdict(q)
        payload["decision"] = q.decision.value
        self._atomic_json(cdir / "qualification.json", payload)

    def promote(self, candidate_id: str) -> Path:
        cdir, _manifest, adapter_digest, manifest_digest = self._verify_candidate_bytes(candidate_id)
        qpath = cdir / "qualification.json"
        if not qpath.exists():
            raise RuntimeError("Candidate has no qualification record")
        q = json.loads(qpath.read_text())
        if q.get("candidate_id") != candidate_id:
            raise RuntimeError("qualification candidate identity mismatch")
        if q.get("decision") != PromotionDecision.PROMOTE.value:
            raise RuntimeError("Candidate is not qualified for promotion")
        if q.get("adapter_digest") != adapter_digest:
            raise RuntimeError("candidate changed after qualification")
        if q.get("candidate_manifest_digest") != manifest_digest:
            raise RuntimeError("candidate manifest changed after qualification")

        dst = (self.promoted / candidate_id).resolve()
        if dst.parent != self.promoted:
            raise RuntimeError("promotion path escapes registry")
        tmp = self.promoted / (candidate_id + ".tmp-" + uuid.uuid4().hex)
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(cdir, tmp)
        if dst.exists():
            shutil.rmtree(dst)
        os.replace(tmp, dst)

        previous = self.current_id()
        generation = self.current_generation() + 1
        state = {
            "current": candidate_id,
            "previous": previous,
            "generation": generation,
            "adapter_digest": adapter_digest,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cache_policy": "REPLAY_REQUIRED",
        }
        self._atomic_json(self.meta / "production.json", state)
        return dst

    def current_id(self) -> str | None:
        p = self.meta / "production.json"
        if not p.exists():
            return None
        return json.loads(p.read_text()).get("current")

    def current_generation(self) -> int:
        p = self.meta / "production.json"
        if not p.exists():
            return 0
        return int(json.loads(p.read_text()).get("generation", 0))

    def rollback(self) -> str:
        p = self.meta / "production.json"
        if not p.exists():
            raise RuntimeError("No production state")
        state = json.loads(p.read_text())
        prev = state.get("previous")
        if not prev:
            raise RuntimeError("No previous promoted adapter to roll back to")
        self._validate_id(prev)
        if not (self.promoted / prev).is_dir():
            raise RuntimeError("previous promoted adapter is missing")
        current = state.get("current")
        state["current"], state["previous"] = prev, current
        state["generation"] = int(state.get("generation", 0)) + 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["cache_policy"] = "REPLAY_REQUIRED"
        self._atomic_json(p, state)
        return prev
