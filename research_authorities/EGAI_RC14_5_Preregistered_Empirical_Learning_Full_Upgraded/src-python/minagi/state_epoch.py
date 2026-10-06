from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from typing import Any

from kvcontinual.execution.durability.file_lock import ProcessFileLock
from minagi.egai.canonical import atomic_write_json, sha256_json


def _digest(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{name} must be a sha256 digest")


@dataclass(frozen=True)
class StateEpoch:
    """Immutable root of all state visible to one request generation."""

    epoch: int
    predecessor_digest: str | None
    foundation_model_digest: str
    tokenizer_digest: str
    runtime_manifest_digest: str
    belief_snapshot_digest: str
    skill_snapshot_digest: str
    memory_policy_digest: str
    retrieval_policy_digest: str
    adapter_set_digest: str
    promotion_decision_digest: str
    created_at: str
    schema: str = "egai-state-epoch-v1"

    @classmethod
    def create(cls, *, epoch: int, predecessor_digest: str | None, foundation_model_digest: str,
               tokenizer_digest: str, runtime_manifest_digest: str, belief_snapshot_digest: str,
               skill_snapshot_digest: str, memory_policy_digest: str, retrieval_policy_digest: str,
               adapter_set_digest: str, promotion_decision_digest: str) -> "StateEpoch":
        obj = cls(int(epoch), predecessor_digest, foundation_model_digest, tokenizer_digest,
                  runtime_manifest_digest, belief_snapshot_digest, skill_snapshot_digest,
                  memory_policy_digest, retrieval_policy_digest, adapter_set_digest,
                  promotion_decision_digest, datetime.now(timezone.utc).isoformat())
        obj.validate()
        return obj

    def validate(self) -> None:
        if self.epoch < 0:
            raise ValueError("epoch must be non-negative")
        if self.predecessor_digest is not None:
            _digest("predecessor_digest", self.predecessor_digest)
        for name in (
            "foundation_model_digest", "tokenizer_digest", "runtime_manifest_digest",
            "belief_snapshot_digest", "skill_snapshot_digest", "memory_policy_digest",
            "retrieval_policy_digest", "adapter_set_digest", "promotion_decision_digest",
        ):
            _digest(name, getattr(self, name))
        if not self.created_at:
            raise ValueError("created_at required")

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_json(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "digest": self.digest}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StateEpoch":
        doc = dict(raw)
        got = str(doc.pop("digest", ""))
        obj = cls(**doc)
        obj.validate()
        if got and got != obj.digest:
            raise RuntimeError("state epoch digest mismatch")
        return obj


class StateEpochRegistry:
    """Prepare immutable epochs, then atomically activate a signed transition."""

    def __init__(self, root: str | Path, *, verifier):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.db_path = self.root / "epochs.sqlite3"
        self.lock_path = self.root / "epochs.lock"
        self.verifier = verifier
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
            c.execute("""CREATE TABLE IF NOT EXISTS state(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), active_digest TEXT,
                epoch INTEGER NOT NULL DEFAULT -1, transition_digest TEXT, updated_at REAL NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS transitions(
                transition_id TEXT PRIMARY KEY, nonce TEXT NOT NULL UNIQUE,
                from_digest TEXT, to_digest TEXT NOT NULL, from_epoch INTEGER NOT NULL,
                to_epoch INTEGER NOT NULL, body_json TEXT NOT NULL, receipt_json TEXT NOT NULL,
                transition_digest TEXT NOT NULL UNIQUE, committed_at REAL NOT NULL)""")
            c.execute("INSERT OR IGNORE INTO state(singleton,epoch,updated_at) VALUES(1,-1,?)", (time.time(),))
            c.commit()

    def _path(self, digest: str) -> Path:
        _digest("epoch digest", digest)
        return self.objects / f"{digest[7:]}.json"

    def prepare(self, epoch: StateEpoch) -> str:
        path = self._path(epoch.digest)
        if not path.exists():
            atomic_write_json(path, epoch.to_dict())
        elif StateEpoch.from_dict(json.loads(path.read_text(encoding="utf-8"))).digest != epoch.digest:
            raise RuntimeError("state epoch CAS collision")
        return epoch.digest

    def get(self, digest: str) -> StateEpoch:
        return StateEpoch.from_dict(json.loads(self._path(digest).read_text(encoding="utf-8")))

    def state(self) -> dict[str, Any]:
        with self._connect() as c:
            return dict(c.execute("SELECT * FROM state WHERE singleton=1").fetchone())

    def active(self) -> StateEpoch | None:
        d = self.state().get("active_digest")
        return None if not d else self.get(str(d))

    @staticmethod
    def transition_body(*, transition_id: str, nonce: str, from_digest: str | None, to_digest: str,
                        from_epoch: int, to_epoch: int, previous_transition_digest: str | None,
                        reason: str) -> dict[str, Any]:
        return {
            "receipt_type": "egai.state-epoch-transition.v1",
            "transition_id": transition_id,
            "nonce": nonce,
            "from_digest": from_digest,
            "to_digest": to_digest,
            "from_epoch": int(from_epoch),
            "to_epoch": int(to_epoch),
            "previous_transition_digest": previous_transition_digest,
            "reason": reason,
        }

    def activate(self, digest: str, receipt: dict[str, Any]) -> dict[str, Any]:
        target = self.get(digest)
        body = receipt.get("body") if isinstance(receipt, dict) else None
        if not isinstance(body, dict) or not self.verifier.verify(receipt, expected_body=body):
            raise PermissionError("invalid state epoch authority receipt")
        if body.get("receipt_type") != "egai.state-epoch-transition.v1" or body.get("to_digest") != digest:
            raise PermissionError("state epoch authorization target mismatch")
        with ProcessFileLock(self.lock_path, timeout=30.0):
            current = self.state()
            if body.get("from_digest") != current.get("active_digest"):
                raise RuntimeError("state epoch predecessor mismatch")
            if int(body.get("from_epoch", -2)) != int(current["epoch"]):
                raise RuntimeError("state epoch source generation mismatch")
            if int(body.get("to_epoch", -2)) != target.epoch or target.epoch <= int(current["epoch"]):
                raise RuntimeError("state epoch must advance monotonically")
            if target.predecessor_digest != current.get("active_digest"):
                raise RuntimeError("state epoch object predecessor mismatch")
            if body.get("previous_transition_digest") != current.get("transition_digest"):
                raise RuntimeError("state epoch transition-chain mismatch")
            transition_id = str(body.get("transition_id") or "")
            nonce = str(body.get("nonce") or "")
            if not transition_id or not nonce:
                raise RuntimeError("state epoch transition id/nonce required")
            td = sha256_json({"body": body, "receipt": receipt})
            try:
                with self._connect() as c:
                    c.execute("BEGIN IMMEDIATE")
                    c.execute("INSERT INTO transitions VALUES(?,?,?,?,?,?,?,?,?,?)", (
                        transition_id, nonce, current.get("active_digest"), digest, int(current["epoch"]),
                        target.epoch, json.dumps(body, sort_keys=True, separators=(",", ":")),
                        json.dumps(receipt, sort_keys=True, separators=(",", ":")), td, time.time()))
                    c.execute("UPDATE state SET active_digest=?,epoch=?,transition_digest=?,updated_at=? WHERE singleton=1",
                              (digest, target.epoch, td, time.time()))
                    c.commit()
            except sqlite3.IntegrityError as exc:
                raise RuntimeError("state epoch transition replay/collision") from exc
        return {"active_digest": digest, "epoch": target.epoch, "transition_digest": td}

    def verify(self) -> dict[str, Any]:
        with self._connect() as c:
            if str(c.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise RuntimeError("state epoch sqlite integrity failure")
            rows = c.execute("SELECT * FROM transitions ORDER BY to_epoch").fetchall()
            state = dict(c.execute("SELECT * FROM state WHERE singleton=1").fetchone())
        prev_digest = None
        prev_epoch = -1
        prev_transition = None
        for r in rows:
            body = json.loads(str(r["body_json"]))
            receipt = json.loads(str(r["receipt_json"]))
            if not self.verifier.verify(receipt, expected_body=body):
                raise RuntimeError("state epoch stored receipt invalid")
            if body.get("from_digest") != prev_digest or int(body["from_epoch"]) != prev_epoch:
                raise RuntimeError("state epoch history discontinuity")
            if body.get("previous_transition_digest") != prev_transition:
                raise RuntimeError("state epoch transition predecessor mismatch")
            target = self.get(str(r["to_digest"]))
            if target.epoch != int(r["to_epoch"]) or target.predecessor_digest != prev_digest:
                raise RuntimeError("state epoch object/history mismatch")
            td = sha256_json({"body": body, "receipt": receipt})
            if td != str(r["transition_digest"]):
                raise RuntimeError("state epoch transition digest mismatch")
            prev_digest, prev_epoch, prev_transition = target.digest, target.epoch, td
        if state.get("active_digest") != prev_digest or int(state["epoch"]) != prev_epoch or state.get("transition_digest") != prev_transition:
            raise RuntimeError("state epoch active pointer mismatch")
        return {"ok": True, "transitions": len(rows), "active_digest": prev_digest, "epoch": prev_epoch}
