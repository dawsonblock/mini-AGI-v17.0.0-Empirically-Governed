from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from kvcontinual.rc1025.cache.block import ExecutionArtifact, HybridMemoryBlock
from kvcontinual.rc1025.cache.identity import compare_execution_identity
from kvcontinual.rc1025.cache.serialization import load_execution_artifact, save_execution_artifact
from kvcontinual.rc1025.recurrent.affine import compose_sequence
from kvcontinual.rc1025.types import CacheIdentity, CacheTier, Compatibility, ExecutionIdentity


@dataclass
class CompositionResult:
    selected_ids: list[str]
    per_layer: dict[object, object]


class ExecutionArtifactStore:
    """Execution cache with optional crash-safe content-addressed persistence.

    ``root=None`` retains the original in-memory behavior. With a root, numeric
    artifact payloads live under ``objects/<content-digest>.npz`` and small
    namespace indexes map ``(source_segment_id, ExecutionIdentity)`` to those
    immutable objects. Index replacement is atomic. Corrupt or identity-mismatched
    objects fail closed and are never returned as cache hits.
    """
    def __init__(self, root: str | Path | None = None):
        self._artifacts: dict[tuple[str, str], ExecutionArtifact] = {}
        self._bytes_by_tier: dict[CacheTier, int] = defaultdict(int)
        self.root = None if root is None else Path(root)
        if self.root is not None:
            (self.root / "objects").mkdir(parents=True, exist_ok=True)
            (self.root / "index").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hex_digest(digest: str) -> str:
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError("expected sha256 digest")
        return digest.split(":", 1)[1]

    @staticmethod
    def _sid_key(source_segment_id: str) -> str:
        return hashlib.sha256(source_segment_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _storage_digest(artifact: ExecutionArtifact) -> str:
        # Qualification is mutable evidence bound to immutable model-derived
        # content. Keep differently qualified copies separate on disk without
        # contaminating ExecutionArtifact.content_digest or creating a digest
        # recursion through ArtifactQualification.artifact_content_digest.
        q = "" if artifact.qualification is None else artifact.qualification.receipt_digest
        raw = (artifact.content_digest + "|" + q).encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def _object_path(self, storage_digest: str) -> Path:
        assert self.root is not None
        return self.root / "objects" / f"{self._hex_digest(storage_digest)}.npz"

    def _index_path(self, source_segment_id: str, identity: ExecutionIdentity) -> Path:
        assert self.root is not None
        return self.root / "index" / self._hex_digest(identity.digest) / f"{self._sid_key(source_segment_id)}.json"

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True, separators=(",", ":"))
            f.flush()
            tmp = Path(f.name)
        tmp.replace(path)

    def _persist(self, artifact: ExecutionArtifact) -> None:
        if self.root is None:
            return
        storage_digest = self._storage_digest(artifact)
        object_path = self._object_path(storage_digest)
        if not object_path.exists():
            object_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix=".npz", dir=object_path.parent, delete=False) as f:
                tmp = Path(f.name)
            try:
                save_execution_artifact(tmp, artifact)
                # Re-open before commit so a partial/corrupt object is never indexed.
                check = load_execution_artifact(tmp)
                if check.content_digest != artifact.content_digest:
                    raise ValueError("persisted artifact digest changed during serialization")
                tmp.replace(object_path)
            finally:
                if tmp.exists():
                    tmp.unlink()
        index_path = self._index_path(artifact.source_segment_id, artifact.identity)
        self._atomic_json(index_path, {
            "source_segment_id": artifact.source_segment_id,
            "execution_identity_digest": artifact.identity.digest,
            "content_digest": artifact.content_digest,
            "storage_digest": storage_digest,
            "qualification_receipt_digest": "" if artifact.qualification is None else artifact.qualification.receipt_digest,
            "artifact_id": artifact.artifact_id,
            "tier": artifact.tier.value,
        })

    def put(self, artifact: ExecutionArtifact) -> None:
        artifact.validate()
        if artifact.byte_size <= 0:
            artifact.recompute_byte_size()
        self._persist(artifact)
        key = (artifact.source_segment_id, artifact.identity.digest)
        old = self._artifacts.get(key)
        if old is not None:
            self._bytes_by_tier[old.tier] -= old.byte_size
        self._artifacts[key] = artifact
        self._bytes_by_tier[artifact.tier] += artifact.byte_size

    def _load_persisted(self, source_segment_id: str, identity: ExecutionIdentity) -> ExecutionArtifact | None:
        if self.root is None:
            return None
        idx = self._index_path(source_segment_id, identity)
        if not idx.exists():
            return None
        try:
            meta = json.loads(idx.read_text(encoding="utf-8"))
            if meta.get("source_segment_id") != source_segment_id:
                raise ValueError("execution-cache index source mismatch")
            if meta.get("execution_identity_digest") != identity.digest:
                raise ValueError("execution-cache index identity mismatch")
            content_digest = str(meta["content_digest"])
            storage_digest = str(meta["storage_digest"])
            obj = self._object_path(storage_digest)
            art = load_execution_artifact(obj)
            if art.source_segment_id != source_segment_id or art.identity.digest != identity.digest:
                raise ValueError("persisted execution artifact key mismatch")
            if art.content_digest != content_digest:
                raise ValueError("persisted execution artifact content mismatch")
            if self._storage_digest(art) != storage_digest:
                raise ValueError("persisted execution artifact storage digest mismatch")
            if "tier" in meta:
                art.tier = CacheTier(meta["tier"])
            self._artifacts[(source_segment_id, identity.digest)] = art
            self._bytes_by_tier[art.tier] += art.byte_size
            return art
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            # A corrupt derived cache entry is disposable. Fail closed; source
            # memory remains authoritative and the runtime can rematerialize it.
            return None

    def get(self, source_segment_id: str, identity: ExecutionIdentity) -> ExecutionArtifact | None:
        hit = self._artifacts.get((source_segment_id, identity.digest))
        return hit if hit is not None else self._load_persisted(source_segment_id, identity)

    def resolve(self, source_segment_ids: list[str], identity: ExecutionIdentity) -> tuple[list[ExecutionArtifact], list[str]]:
        hits, misses = [], []
        for sid in source_segment_ids:
            a = self.get(sid, identity)
            (hits if a is not None else misses).append(a if a is not None else sid)
        return hits, misses

    def compatible_candidates(self, source_segment_id: str, identity: ExecutionIdentity):
        out = []
        for (sid, _), art in self._artifacts.items():
            if sid == source_segment_id:
                out.append((art, compare_execution_identity(art.identity, identity)))
        return out

    def move_tier(self, source_segment_id: str, identity: ExecutionIdentity, tier: CacheTier) -> None:
        art = self.get(source_segment_id, identity)
        if art is None:
            raise KeyError(source_segment_id)
        if art.tier == tier:
            return
        self._bytes_by_tier[art.tier] -= art.byte_size
        art.tier = tier
        self._bytes_by_tier[tier] += art.byte_size
        # Tier is placement metadata, not content. Rewrite only the index.
        if self.root is not None:
            idx = self._index_path(source_segment_id, identity)
            meta = json.loads(idx.read_text(encoding="utf-8"))
            meta["tier"] = tier.value
            self._atomic_json(idx, meta)

    def evict_namespace(self, identity: ExecutionIdentity) -> int:
        doomed = [k for k, v in self._artifacts.items() if v.identity.digest == identity.digest]
        for key in doomed:
            art = self._artifacts.pop(key)
            self._bytes_by_tier[art.tier] -= art.byte_size
        count = len(doomed)
        if self.root is not None:
            ns = self.root / "index" / self._hex_digest(identity.digest)
            if ns.exists():
                count = max(count, len(list(ns.glob("*.json"))))
                shutil.rmtree(ns)
        return count

    def gc(self) -> int:
        """Delete unreferenced CAS objects. Returns object count removed."""
        if self.root is None:
            return 0
        referenced: set[str] = set()
        for idx in (self.root / "index").glob("*/*.json"):
            try:
                meta = json.loads(idx.read_text(encoding="utf-8"))
                referenced.add(self._hex_digest(str(meta["storage_digest"])))
            except Exception:
                continue
        removed = 0
        for obj in (self.root / "objects").glob("*.npz"):
            if obj.stem not in referenced:
                obj.unlink()
                removed += 1
        return removed

    def bytes_by_tier(self) -> dict[str, int]:
        return {k.value: int(v) for k, v in self._bytes_by_tier.items()}

    def compose_fixed_input_tails(self, source_segment_ids: list[str], identity: ExecutionIdentity):
        """Research-only algebra check; not the arbitrary-PIC runtime path."""
        arts = [self.get(sid, identity) for sid in source_segment_ids]
        if any(a is None for a in arts):
            raise KeyError("missing execution artifact")
        common = set(arts[0].recurrent)
        for art in arts[1:]:
            common &= set(art.recurrent)
        return {key: compose_sequence([art.recurrent[key].tail_summary for art in arts]) for key in sorted(common)}


class BlockStore:
    """Legacy RC10 block store, preserved for migration tooling."""
    def __init__(self):
        self._blocks: dict[str, HybridMemoryBlock] = {}

    def put(self, block: HybridMemoryBlock) -> None:
        self._blocks[block.block_id] = block

    def get(self, block_id: str) -> HybridMemoryBlock:
        return self._blocks[block_id]

    def compose(self, block_ids: list[str], expected_identity: CacheIdentity) -> CompositionResult:
        if not block_ids:
            raise ValueError("block_ids cannot be empty")
        blocks = [self.get(i) for i in block_ids]
        for b in blocks:
            if b.cache_identity != expected_identity:
                raise ValueError(f"Cache identity mismatch for block {b.block_id}")
        common_layers = set(blocks[0].recurrence)
        for b in blocks[1:]:
            common_layers &= set(b.recurrence)
        per_layer = {layer: compose_sequence([b.recurrence[layer] for b in blocks]) for layer in sorted(common_layers)}
        return CompositionResult(selected_ids=block_ids, per_layer=per_layer)
