from __future__ import annotations

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any

from kvcontinual.execution.durability.file_lock import ProcessFileLock
from .canonical import atomic_write_json, sha256_json
from .models import Belief, BeliefStatus, PromotionVerdict


class BeliefRepository:
    """Immutable belief revisions with a transactional active head per belief_id."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.candidates = self.root / "candidates"
        self.objects = self.root / "objects"
        self.db_path = self.root / "beliefs.sqlite3"
        self.lock_path = self.root / "beliefs.lock"
        self.candidates.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        c = sqlite3.connect(self.db_path, timeout=30.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        return c

    def _init_db(self):
        with self._connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS revisions(
                digest TEXT PRIMARY KEY, belief_id TEXT NOT NULL,
                statement_digest TEXT NOT NULL, qualification_digest TEXT NOT NULL,
                predecessor_digest TEXT, promoted_at REAL NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS belief_revision_id_idx ON revisions(belief_id,promoted_at)")
            c.execute("""CREATE TABLE IF NOT EXISTS heads(
                belief_id TEXT PRIMARY KEY, digest TEXT NOT NULL, updated_at REAL NOT NULL)""")
            c.commit()

    @staticmethod
    def _doc(belief: Belief) -> dict[str, Any]:
        doc = asdict(belief)
        doc["status"] = belief.status.value
        doc["digest"] = belief.digest
        return doc

    @staticmethod
    def _load_doc(path: Path) -> Belief:
        doc = json.loads(path.read_text(encoding="utf-8"))
        got = str(doc.pop("digest", ""))
        doc["status"] = BeliefStatus(str(doc["status"]))
        belief = Belief(**doc)
        if belief.digest != got:
            raise RuntimeError("belief digest mismatch")
        return belief

    def _object_path(self, digest: str) -> Path:
        return self.objects / f"{str(digest).removeprefix('sha256:')}.json"

    def register_candidate(self, belief: Belief) -> str:
        if belief.status is not BeliefStatus.CANDIDATE:
            raise ValueError("only candidate beliefs may be registered by the learning plane")
        path = self.candidates / f"{belief.digest.removeprefix('sha256:')}.json"
        if path.exists():
            existing = self._load_doc(path)
            if existing != belief:
                raise RuntimeError("belief candidate digest collision")
            return belief.digest
        atomic_write_json(path, self._doc(belief))
        return belief.digest

    def promote(self, candidate_digest: str, authorization: dict[str, Any], verifier: Any) -> Belief:
        stem = str(candidate_digest).removeprefix("sha256:")
        candidate = self._load_doc(self.candidates / f"{stem}.json")
        body = dict(authorization.get("body") or {})
        if not verifier.verify(authorization, expected_body=body):
            raise PermissionError("invalid promotion authorization")
        if body.get("schema") != "mini-agi-egai-promotion-authorization-v2":
            raise PermissionError("unsupported promotion authorization schema")
        if body.get("candidate_digest") != candidate.digest:
            raise PermissionError("promotion authorization candidate mismatch")
        if body.get("verdict") != PromotionVerdict.APPROVE.value:
            raise PermissionError("promotion authorization is not approval")
        promoted = replace(candidate, status=BeliefStatus.PROMOTED, qualification_digest=str(body["qualification_digest"]))
        obj = self._object_path(promoted.digest)
        with ProcessFileLock(self.lock_path, timeout=30.0):
            if not obj.exists():
                atomic_write_json(obj, self._doc(promoted))
            elif self._load_doc(obj) != promoted:
                raise RuntimeError("belief promoted-object collision")
            with self._connect() as c:
                c.execute("BEGIN IMMEDIATE")
                head = c.execute("SELECT digest FROM heads WHERE belief_id=?", (promoted.belief_id,)).fetchone()
                predecessor = None if head is None else str(head["digest"])
                c.execute(
                    "INSERT OR IGNORE INTO revisions(digest,belief_id,statement_digest,qualification_digest,predecessor_digest,promoted_at) VALUES(?,?,?,?,?,?)",
                    (promoted.digest, promoted.belief_id, promoted.statement_digest, promoted.qualification_digest, predecessor, time.time()),
                )
                c.execute(
                    "INSERT INTO heads(belief_id,digest,updated_at) VALUES(?,?,?) ON CONFLICT(belief_id) DO UPDATE SET digest=excluded.digest,updated_at=excluded.updated_at",
                    (promoted.belief_id, promoted.digest, time.time()),
                )
                c.commit()
        return promoted

    def load_promoted(self, belief_id: str) -> Belief:
        with self._connect() as c:
            row = c.execute("SELECT digest FROM heads WHERE belief_id=?", (belief_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(belief_id)
        belief = self._load_doc(self._object_path(str(row["digest"])))
        if belief.status is not BeliefStatus.PROMOTED:
            raise RuntimeError("belief head contains non-promoted record")
        return belief

    def load_revision(self, digest: str) -> Belief:
        return self._load_doc(self._object_path(digest))

    def history(self, belief_id: str) -> tuple[str, ...]:
        with self._connect() as c:
            rows = c.execute("SELECT digest FROM revisions WHERE belief_id=? ORDER BY promoted_at,digest", (belief_id,)).fetchall()
        return tuple(str(r["digest"]) for r in rows)

    def snapshot(self) -> dict[str, str]:
        with self._connect() as c:
            rows = c.execute("SELECT belief_id,digest FROM heads ORDER BY belief_id").fetchall()
        return {str(r["belief_id"]): str(r["digest"]) for r in rows}

    @property
    def snapshot_digest(self) -> str:
        return sha256_json(self.snapshot())

    def verify(self) -> dict[str, Any]:
        with self._connect() as c:
            if str(c.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise RuntimeError("belief repository sqlite integrity failure")
            rows = c.execute("SELECT * FROM revisions ORDER BY promoted_at,digest").fetchall()
            heads = c.execute("SELECT * FROM heads ORDER BY belief_id").fetchall()
        known = {str(r["digest"]) for r in rows}
        for r in rows:
            belief = self._load_doc(self._object_path(str(r["digest"])))
            if belief.belief_id != str(r["belief_id"]):
                raise RuntimeError("belief index/object mismatch")
        for h in heads:
            if str(h["digest"]) not in known:
                raise RuntimeError("belief head references missing revision")
        return {"ok": True, "revisions": len(rows), "heads": len(heads), "snapshot_digest": self.snapshot_digest}
