from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping

from kvcontinual.execution.durability.file_lock import ProcessFileLock
from .canonical import sha256_json
from .models import LearningLevel, PromotionVerdict

GENESIS = "0" * 64
EVENT_SCHEMA = "egai-improvement-event-v3"


@dataclass(frozen=True)
class ImprovementRecord:
    improvement_id: str
    proposal_digest: str
    candidate_digest: str
    qualification_digest: str
    promotion_decision_digest: str
    verdict: PromotionVerdict
    level: LearningLevel
    origin_evidence: tuple[str, ...]
    affected_components: tuple[str, ...]
    metrics: Mapping[str, float]
    production_identity_before: str
    production_identity_after: str = ""
    rollback_target: str = ""
    created_at: float = 0.0
    schema: str = "mini-agi-egai-improvement-record-v2"

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin_evidence", tuple(self.origin_evidence))
        object.__setattr__(self, "affected_components", tuple(self.affected_components))
        object.__setattr__(self, "metrics", {str(k): float(v) for k, v in dict(self.metrics).items()})
        if not self.created_at:
            object.__setattr__(self, "created_at", float(time.time()))

    @property
    def digest(self) -> str:
        body = asdict(self)
        body["verdict"] = self.verdict.value
        body["level"] = int(self.level)
        return sha256_json(body)


@dataclass(frozen=True)
class FutureConsequence:
    improvement_digest: str
    observation_horizon: str
    forward_transfer: float
    retention_delta: float
    calibration_delta: float
    compute_delta: float
    capacity_delta: float
    rollback_triggered: bool = False
    notes: str = ""
    schema: str = "mini-agi-egai-future-consequence-v2"

    @property
    def digest(self) -> str:
        return sha256_json(asdict(self))


class ImprovementLedger:
    """Transactional improvement ledger backed by SQLite WAL.

    The constructor keeps the old path-shaped API for compatibility, but the
    authoritative state lives in ``<path>.sqlite3``. This avoids append races and
    ambiguous post-commit failures under concurrent promotion/evaluation work.
    """

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = self.path.with_name(self.path.name + ".sqlite3")
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self._init_db()
        self.verify()

    def _connect(self):
        c = sqlite3.connect(self.db_path, timeout=30.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        return c

    def _init_db(self):
        with self._connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS state(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), seq INTEGER NOT NULL,
                head TEXT NOT NULL, updated_at REAL NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL, prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE, committed_at REAL NOT NULL)""")
            c.execute("INSERT OR IGNORE INTO state(singleton,seq,head,updated_at) VALUES(1,0,?,?)", (GENESIS, time.time()))
            c.commit()

    def _events(self) -> list[dict[str, Any]]:
        with self._connect() as c:
            rows = c.execute("SELECT * FROM events ORDER BY seq").fetchall()
            state = c.execute("SELECT seq,head FROM state WHERE singleton=1").fetchone()
        out = []
        prev = GENESIS
        for n, r in enumerate(rows, 1):
            if int(r["seq"]) != n:
                raise RuntimeError("improvement sequence gap")
            payload = json.loads(str(r["payload_json"]))
            if sha256_json(payload) != str(r["payload_digest"]):
                raise RuntimeError("improvement payload digest mismatch")
            body = {
                "schema": EVENT_SCHEMA,
                "seq": n,
                "kind": str(r["kind"]),
                "payload_digest": str(r["payload_digest"]),
                "prev": prev,
            }
            want = sha256_json(body).removeprefix("sha256:")
            if want != str(r["event_hash"]) or str(r["prev_hash"]) != prev:
                raise RuntimeError("improvement hash-chain failure")
            out.append({**body, "payload": payload, "hash": want})
            prev = want
        if int(state["seq"]) != len(out) or str(state["head"]) != (out[-1]["hash"] if out else GENESIS):
            raise RuntimeError("improvement state/head mismatch")
        return out

    def _append(self, kind: str, payload: Mapping[str, Any]) -> str:
        payload = dict(payload)
        pd = sha256_json(payload)
        with ProcessFileLock(self.lock_path, timeout=30.0):
            with self._connect() as c:
                c.execute("BEGIN IMMEDIATE")
                state = c.execute("SELECT seq,head FROM state WHERE singleton=1").fetchone()
                seq = int(state["seq"]) + 1
                prev = str(state["head"])
                body = {"schema": EVENT_SCHEMA, "seq": seq, "kind": str(kind), "payload_digest": pd, "prev": prev}
                eh = sha256_json(body).removeprefix("sha256:")
                c.execute(
                    "INSERT INTO events(seq,kind,payload_json,payload_digest,prev_hash,event_hash,committed_at) VALUES(?,?,?,?,?,?,?)",
                    (seq, str(kind), json.dumps(payload, sort_keys=True, separators=(",", ":")), pd, prev, eh, time.time()),
                )
                c.execute("UPDATE state SET seq=?,head=?,updated_at=? WHERE singleton=1", (seq, eh, time.time()))
                c.commit()
        return eh

    def append_improvement(self, record: ImprovementRecord) -> str:
        body = asdict(record)
        body["verdict"] = record.verdict.value
        body["level"] = int(record.level)
        body["digest"] = record.digest
        return self._append("decision", body)

    def append_consequence(self, consequence: FutureConsequence) -> str:
        body = asdict(consequence)
        body["digest"] = consequence.digest
        known = {str(e["payload"].get("digest")) for e in self._events() if e["kind"] == "decision"}
        if consequence.improvement_digest not in known:
            raise ValueError("future consequence references unknown improvement")
        return self._append("future_consequence", body)

    def verify(self) -> dict[str, Any]:
        with self._connect() as c:
            integrity = str(c.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise RuntimeError(f"improvement sqlite integrity failure: {integrity}")
        events = self._events()
        known: set[str] = set()
        for event in events:
            payload = dict(event["payload"])
            digest = str(payload.pop("digest", ""))
            if not digest or sha256_json(payload) != digest:
                raise RuntimeError("improvement object digest mismatch")
            if event["kind"] == "decision":
                known.add(digest)
            elif event["kind"] == "future_consequence":
                if str(payload.get("improvement_digest", "")) not in known:
                    raise RuntimeError("future consequence precedes or misses improvement decision")
            else:
                raise RuntimeError("unknown improvement ledger event kind")
        return {
            "ok": True,
            "events": len(events),
            "decisions": sum(x["kind"] == "decision" for x in events),
            "future_consequences": sum(x["kind"] == "future_consequence" for x in events),
            "head": events[-1]["hash"] if events else GENESIS,
        }

    def meta_learning_rows(self) -> list[dict[str, Any]]:
        events = self._events()
        decisions = {str(e["payload"]["digest"]): dict(e["payload"]) for e in events if e["kind"] == "decision"}
        rows = []
        for event in events:
            if event["kind"] == "future_consequence":
                c = dict(event["payload"])
                rows.append({"decision": decisions[str(c["improvement_digest"])], "future_consequence": c})
        return rows
