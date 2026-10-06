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
from .models import PromotionVerdict, SkillManifest


class SkillRepository:
    """Immutable promoted skill revisions with a transactional active head."""

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.candidates = self.root / "candidates"
        self.objects = self.root / "objects"
        self.db_path = self.root / "skills.sqlite3"
        self.lock_path = self.root / "skills.lock"
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
                digest TEXT PRIMARY KEY, skill_id TEXT NOT NULL, version INTEGER NOT NULL,
                qualification_digest TEXT NOT NULL, predecessor_digest TEXT,
                promoted_at REAL NOT NULL, UNIQUE(skill_id,version))""")
            c.execute("""CREATE TABLE IF NOT EXISTS heads(
                skill_id TEXT PRIMARY KEY, digest TEXT NOT NULL, version INTEGER NOT NULL,
                updated_at REAL NOT NULL)""")
            c.commit()

    @staticmethod
    def _doc(skill: SkillManifest) -> dict[str, Any]:
        return {**asdict(skill), "digest": skill.digest}

    @staticmethod
    def _load_doc(path: Path) -> SkillManifest:
        doc = json.loads(path.read_text(encoding="utf-8"))
        got = str(doc.pop("digest", ""))
        skill = SkillManifest(**doc)
        if skill.digest != got:
            raise RuntimeError("skill manifest digest mismatch")
        return skill

    def _object_path(self, digest: str) -> Path:
        return self.objects / f"{str(digest).removeprefix('sha256:')}.json"

    def register_candidate(self, skill: SkillManifest) -> str:
        path = self.candidates / f"{skill.digest.removeprefix('sha256:')}.json"
        if path.exists():
            existing = self._load_doc(path)
            if existing != skill:
                raise RuntimeError("skill candidate digest collision")
            return skill.digest
        atomic_write_json(path, self._doc(skill))
        return skill.digest

    def promote(self, candidate_digest: str, authorization: dict[str, Any], verifier: Any) -> SkillManifest:
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
        qualified = replace(candidate, qualification_digest=str(body["qualification_digest"]))
        obj = self._object_path(qualified.digest)
        with ProcessFileLock(self.lock_path, timeout=30.0):
            if not obj.exists():
                atomic_write_json(obj, self._doc(qualified))
            elif self._load_doc(obj) != qualified:
                raise RuntimeError("skill promoted-object collision")
            with self._connect() as c:
                c.execute("BEGIN IMMEDIATE")
                head = c.execute("SELECT digest,version FROM heads WHERE skill_id=?", (qualified.skill_id,)).fetchone()
                predecessor = None if head is None else str(head["digest"])
                if head is not None:
                    hv = int(head["version"])
                    if qualified.version < hv:
                        raise RuntimeError("skill version regression")
                    if qualified.version == hv and predecessor != qualified.digest:
                        raise RuntimeError("conflicting promoted skill revision for same skill_id/version")
                c.execute(
                    "INSERT OR IGNORE INTO revisions(digest,skill_id,version,qualification_digest,predecessor_digest,promoted_at) VALUES(?,?,?,?,?,?)",
                    (qualified.digest, qualified.skill_id, int(qualified.version), qualified.qualification_digest, predecessor, time.time()),
                )
                c.execute(
                    "INSERT INTO heads(skill_id,digest,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(skill_id) DO UPDATE SET digest=excluded.digest,version=excluded.version,updated_at=excluded.updated_at",
                    (qualified.skill_id, qualified.digest, int(qualified.version), time.time()),
                )
                c.commit()
        return qualified

    def load_promoted(self, skill_id: str, version: int) -> SkillManifest:
        with self._connect() as c:
            row = c.execute("SELECT digest FROM revisions WHERE skill_id=? AND version=?", (skill_id, int(version))).fetchone()
        if row is None:
            raise FileNotFoundError(f"{skill_id}@{version}")
        return self._load_doc(self._object_path(str(row["digest"])))

    def load_active(self, skill_id: str) -> SkillManifest:
        with self._connect() as c:
            row = c.execute("SELECT digest FROM heads WHERE skill_id=?", (skill_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(skill_id)
        return self._load_doc(self._object_path(str(row["digest"])))

    def snapshot(self) -> dict[str, str]:
        with self._connect() as c:
            rows = c.execute("SELECT skill_id,digest FROM heads ORDER BY skill_id").fetchall()
        return {str(r["skill_id"]): str(r["digest"]) for r in rows}

    @property
    def snapshot_digest(self) -> str:
        return sha256_json(self.snapshot())

    def verify(self) -> dict[str, Any]:
        with self._connect() as c:
            if str(c.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise RuntimeError("skill repository sqlite integrity failure")
            rows = c.execute("SELECT * FROM revisions ORDER BY skill_id,version").fetchall()
            heads = c.execute("SELECT * FROM heads ORDER BY skill_id").fetchall()
        for r in rows:
            skill = self._load_doc(self._object_path(str(r["digest"])))
            if skill.skill_id != str(r["skill_id"]) or int(skill.version) != int(r["version"]):
                raise RuntimeError("skill index/object mismatch")
        for h in heads:
            if not any(str(r["digest"]) == str(h["digest"]) for r in rows):
                raise RuntimeError("skill head references missing revision")
        return {"ok": True, "revisions": len(rows), "heads": len(heads), "snapshot_digest": self.snapshot_digest}
