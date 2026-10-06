from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid
from typing import Any


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class PromotionWalRecord:
    version: int
    sequence: int
    kind: str
    tx_id: str
    action: str
    candidate_id: str
    previous_record_digest: str
    state_digest: str
    payload: dict[str, Any]
    created_at: str
    record_digest: str = ""

    def _payload(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("record_digest", None)
        return d

    def expected_digest(self) -> str:
        return digest_json(self._payload())

    @property
    def valid(self) -> bool:
        return (
            self.version == 1
            and self.kind in {"PREPARE", "COMMIT", "ABORT"}
            and self.sequence >= 1
            and bool(self.tx_id)
            and self.state_digest.startswith("sha256:")
            and self.record_digest == self.expected_digest()
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "record_digest": self.record_digest}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PromotionWalRecord":
        return cls(
            version=int(raw["version"]),
            sequence=int(raw["sequence"]),
            kind=str(raw["kind"]),
            tx_id=str(raw["tx_id"]),
            action=str(raw["action"]),
            candidate_id=str(raw["candidate_id"]),
            previous_record_digest=str(raw.get("previous_record_digest", "")),
            state_digest=str(raw["state_digest"]),
            payload=dict(raw.get("payload", {})),
            created_at=str(raw["created_at"]),
            record_digest=str(raw.get("record_digest", "")),
        )


class PromotionWal:
    """Hash-chained write-ahead log for production model/cache pointer changes.

    PREPARE includes both before/after production states. COMMIT proves that the
    after-state was durably installed. ABORT records an explicitly abandoned
    transition. The log is append-only and fsync'd on every record.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _records_unchecked(self) -> list[PromotionWalRecord]:
        out: list[PromotionWalRecord] = []
        if not self.path.exists():
            return out
        for lineno, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                out.append(PromotionWalRecord.from_dict(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"invalid promotion WAL JSON at line {lineno}: {exc}") from exc
        return out

    def audit(self) -> list[PromotionWalRecord]:
        records = self._records_unchecked()
        prev = ""
        prepared: dict[str, PromotionWalRecord] = {}
        terminal: set[str] = set()
        for i, r in enumerate(records, 1):
            if not r.valid:
                raise ValueError(f"invalid promotion WAL record at sequence {r.sequence}")
            if r.sequence != i:
                raise ValueError(f"promotion WAL sequence mismatch: expected {i}, got {r.sequence}")
            if r.previous_record_digest != prev:
                raise ValueError(f"promotion WAL hash-chain mismatch at sequence {r.sequence}")
            if r.kind == "PREPARE":
                if r.tx_id in prepared or r.tx_id in terminal:
                    raise ValueError(f"duplicate promotion transaction {r.tx_id}")
                before = r.payload.get("before_state")
                after = r.payload.get("after_state")
                if not isinstance(before, dict) or not isinstance(after, dict):
                    raise ValueError("PREPARE record lacks before/after state")
                if digest_json(after) != r.state_digest:
                    raise ValueError("PREPARE state digest mismatch")
                prepared[r.tx_id] = r
            else:
                p = prepared.get(r.tx_id)
                if p is None:
                    raise ValueError(f"terminal promotion record without PREPARE: {r.tx_id}")
                if r.tx_id in terminal:
                    raise ValueError(f"duplicate terminal promotion record: {r.tx_id}")
                if r.action != p.action or r.candidate_id != p.candidate_id:
                    raise ValueError("terminal promotion record metadata mismatch")
                if r.state_digest != p.state_digest:
                    raise ValueError("terminal promotion state digest mismatch")
                terminal.add(r.tx_id)
            prev = r.record_digest
        return records

    @property
    def head_digest(self) -> str:
        records = self.audit()
        return records[-1].record_digest if records else ""

    def _append(self, record: PromotionWalRecord) -> PromotionWalRecord:
        records = self.audit()
        sequence = len(records) + 1
        prev = records[-1].record_digest if records else ""
        record = replace(record, sequence=sequence, previous_record_digest=prev)
        record = replace(record, record_digest=record.expected_digest())
        raw = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        return record

    def prepare(self, *, action: str, candidate_id: str, before_state: dict[str, Any], after_state: dict[str, Any]) -> PromotionWalRecord:
        if action not in {"PROMOTE", "ROLLBACK"}:
            raise ValueError("unsupported promotion WAL action")
        tx_id = str(uuid.uuid4())
        return self._append(PromotionWalRecord(
            version=1,
            sequence=0,
            kind="PREPARE",
            tx_id=tx_id,
            action=action,
            candidate_id=candidate_id,
            previous_record_digest="",
            state_digest=digest_json(after_state),
            payload={"before_state": before_state, "after_state": after_state},
            created_at=datetime.now(timezone.utc).isoformat(),
        ))

    def commit(self, prepare: PromotionWalRecord, installed_state: dict[str, Any]) -> PromotionWalRecord:
        if prepare.kind != "PREPARE":
            raise ValueError("commit requires PREPARE record")
        if digest_json(installed_state) != prepare.state_digest:
            raise ValueError("installed production state does not match prepared state")
        return self._append(PromotionWalRecord(
            version=1,
            sequence=0,
            kind="COMMIT",
            tx_id=prepare.tx_id,
            action=prepare.action,
            candidate_id=prepare.candidate_id,
            previous_record_digest="",
            state_digest=prepare.state_digest,
            payload={"prepare_digest": prepare.record_digest},
            created_at=datetime.now(timezone.utc).isoformat(),
        ))

    def abort(self, prepare: PromotionWalRecord, reason: str) -> PromotionWalRecord:
        if prepare.kind != "PREPARE":
            raise ValueError("abort requires PREPARE record")
        return self._append(PromotionWalRecord(
            version=1,
            sequence=0,
            kind="ABORT",
            tx_id=prepare.tx_id,
            action=prepare.action,
            candidate_id=prepare.candidate_id,
            previous_record_digest="",
            state_digest=prepare.state_digest,
            payload={"prepare_digest": prepare.record_digest, "reason": str(reason)},
            created_at=datetime.now(timezone.utc).isoformat(),
        ))

    def pending(self) -> list[PromotionWalRecord]:
        records = self.audit()
        prepares = {r.tx_id: r for r in records if r.kind == "PREPARE"}
        terminal = {r.tx_id for r in records if r.kind in {"COMMIT", "ABORT"}}
        return [p for tx, p in prepares.items() if tx not in terminal]

    def latest_committed_state_digest(self) -> str:
        records = self.audit()
        prepares = {r.tx_id: r for r in records if r.kind == "PREPARE"}
        latest = ""
        for r in records:
            if r.kind == "COMMIT":
                latest = prepares[r.tx_id].state_digest
        return latest

    def audit_installed_state(self, state: dict[str, Any]) -> None:
        pending = self.pending()
        if pending:
            raise ValueError(f"promotion WAL has {len(pending)} unresolved transaction(s)")
        expected = self.latest_committed_state_digest()
        if not expected:
            if state:
                raise ValueError("production state exists without committed promotion WAL record")
            return
        actual = digest_json(state)
        if actual != expected:
            raise ValueError("installed production state does not match promotion WAL head")

    @staticmethod
    def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
            tmp = Path(f.name)
        os.replace(tmp, path)
        try:
            dfd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
