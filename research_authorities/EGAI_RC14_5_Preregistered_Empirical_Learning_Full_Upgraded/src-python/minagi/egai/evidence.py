from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping, Sequence
import uuid

from kvcontinual.execution.durability.file_lock import ProcessFileLock
from .canonical import atomic_write_json, sha256_json
from .models import EvidenceClass, EvidenceOrigin, EvidenceRecord

GENESIS = "0" * 64
EVENT_SCHEMA = "egai-evidence-event-v3"
_INGEST_CAPABILITY = object()


class EvidenceLedger:
    """Transactional content-addressed evidence ledger.

    CAS payload/record files are written before the authoritative SQLite commit.
    A crash may therefore leave harmless unreferenced CAS objects, but a caller
    can never receive a failure after an ambiguous partially committed ledger
    transition. The SQLite WAL is authoritative; JSON files are immutable data.
    """

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.records = self.root / "records"
        self.payloads = self.root / "payloads"
        self.db_path = self.root / "ledger.sqlite3"
        self.lock_path = self.root / "ledger.lock"
        self.records.mkdir(parents=True, exist_ok=True)
        self.payloads.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.verify()

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=30.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _init_db(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS state(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                seq INTEGER NOT NULL DEFAULT 0,
                head TEXT NOT NULL,
                updated_at REAL NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY,
                record_digest TEXT NOT NULL UNIQUE,
                payload_digest TEXT NOT NULL,
                event_json TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                prev_hash TEXT NOT NULL,
                committed_at REAL NOT NULL)""")
            c.execute("INSERT OR IGNORE INTO state(singleton,seq,head,updated_at) VALUES(1,0,?,?)", (GENESIS, time.time()))
            c.commit()

    @staticmethod
    def _record_doc(record: EvidenceRecord) -> dict[str, Any]:
        doc = asdict(record)
        doc["origin_class"] = record.origin_class.value
        doc["evidence_class"] = record.evidence_class.value
        doc["digest"] = record.digest
        return doc

    @staticmethod
    def _record_from_doc(doc: Mapping[str, Any]) -> EvidenceRecord:
        body = dict(doc)
        got = str(body.pop("digest", ""))
        body["origin_class"] = EvidenceOrigin(str(body["origin_class"]))
        body["evidence_class"] = EvidenceClass(str(body["evidence_class"]))
        record = EvidenceRecord(**body)
        if got != record.digest:
            raise RuntimeError("evidence record digest mismatch")
        return record

    def _events(self) -> list[dict[str, Any]]:
        with self._connect() as c:
            rows = c.execute("SELECT seq,event_json,event_hash,prev_hash FROM events ORDER BY seq").fetchall()
            state = c.execute("SELECT seq,head FROM state WHERE singleton=1").fetchone()
        out: list[dict[str, Any]] = []
        prev = GENESIS
        for expected_seq, row in enumerate(rows, 1):
            if int(row["seq"]) != expected_seq:
                raise RuntimeError(f"evidence sequence gap at {expected_seq}")
            event = json.loads(str(row["event_json"]))
            if event.get("schema") != EVENT_SCHEMA or event.get("seq") != expected_seq or event.get("prev") != prev:
                raise RuntimeError(f"evidence event chain/schema failure at sequence {expected_seq}")
            body = dict(event)
            got = str(body.pop("hash", ""))
            want = sha256_json(body).removeprefix("sha256:")
            if got != want or got != str(row["event_hash"]) or str(row["prev_hash"]) != prev:
                raise RuntimeError(f"evidence event hash mismatch at sequence {expected_seq}")
            out.append(event)
            prev = got
        if int(state["seq"]) != len(out) or str(state["head"]) != (out[-1]["hash"] if out else GENESIS):
            raise RuntimeError("evidence state/head mismatch")
        return out

    def _append_trusted(self, record: EvidenceRecord, payload: Any, *, capability: object, actor: str) -> str:
        if capability is not _INGEST_CAPABILITY:
            raise PermissionError("evidence mutation requires trusted-ingestor capability")
        if sha256_json(payload) != record.payload_digest:
            raise ValueError("payload digest does not match evidence record")

        record_stem = record.digest.removeprefix("sha256:")
        payload_stem = record.payload_digest.removeprefix("sha256:")
        record_path = self.records / f"{record_stem}.json"
        payload_path = self.payloads / f"{payload_stem}.json"

        with ProcessFileLock(self.lock_path, timeout=30.0):
            # Immutable CAS preparation. Orphans caused by pre-commit crashes are safe.
            if not payload_path.exists():
                atomic_write_json(payload_path, payload)
            elif sha256_json(json.loads(payload_path.read_text(encoding="utf-8"))) != record.payload_digest:
                raise RuntimeError("payload content-address collision")

            if not record_path.exists():
                atomic_write_json(record_path, self._record_doc(record))
            else:
                existing = self._record_from_doc(json.loads(record_path.read_text(encoding="utf-8")))
                if existing != record:
                    raise RuntimeError("evidence digest collision")

            with self._connect() as c:
                c.execute("BEGIN IMMEDIATE")
                existing = c.execute("SELECT record_digest FROM events WHERE record_digest=?", (record.digest,)).fetchone()
                if existing is not None:
                    c.commit()
                    return record.digest
                state = c.execute("SELECT seq,head FROM state WHERE singleton=1").fetchone()
                seq = int(state["seq"]) + 1
                prev = str(state["head"])
                event = {
                    "schema": EVENT_SCHEMA,
                    "seq": seq,
                    "ts": time.time(),
                    "record_digest": record.digest,
                    "payload_digest": record.payload_digest,
                    "origin_class": record.origin_class.value,
                    "evidence_class": record.evidence_class.value,
                    "promotion_eligible": record.promotion_eligible,
                    "actor": str(actor),
                    "prev": prev,
                }
                event["hash"] = sha256_json(event).removeprefix("sha256:")
                event_json = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                c.execute(
                    "INSERT INTO events(seq,record_digest,payload_digest,event_json,event_hash,prev_hash,committed_at) VALUES(?,?,?,?,?,?,?)",
                    (seq, record.digest, record.payload_digest, event_json, event["hash"], prev, time.time()),
                )
                c.execute("UPDATE state SET seq=?,head=?,updated_at=? WHERE singleton=1", (seq, event["hash"], time.time()))
                c.commit()
        return record.digest

    def load(self, digest: str) -> EvidenceRecord:
        stem = str(digest).removeprefix("sha256:")
        return self._record_from_doc(json.loads((self.records / f"{stem}.json").read_text(encoding="utf-8")))

    def load_payload(self, record_or_digest: EvidenceRecord | str) -> Any:
        record = record_or_digest if isinstance(record_or_digest, EvidenceRecord) else self.load(str(record_or_digest))
        stem = record.payload_digest.removeprefix("sha256:")
        value = json.loads((self.payloads / f"{stem}.json").read_text(encoding="utf-8"))
        if sha256_json(value) != record.payload_digest:
            raise RuntimeError("evidence payload digest mismatch")
        return value

    def list_digests(self) -> list[str]:
        return [str(e["record_digest"]) for e in self._events()]

    def verify(self) -> dict[str, Any]:
        with self._connect() as c:
            integrity = str(c.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise RuntimeError(f"evidence sqlite integrity failure: {integrity}")
        events = self._events()
        referenced_records: set[str] = set()
        referenced_payloads: set[str] = set()
        for event in events:
            digest = str(event["record_digest"])
            record = self.load(digest)
            payload = self.load_payload(record)
            if sha256_json(payload) != record.payload_digest:
                raise RuntimeError("evidence payload verification failed")
            if str(event["payload_digest"]) != record.payload_digest:
                raise RuntimeError("evidence event payload binding mismatch")
            if bool(event.get("promotion_eligible")) != record.promotion_eligible:
                raise RuntimeError("evidence promotion eligibility mismatch")
            referenced_records.add(digest.removeprefix("sha256:"))
            referenced_payloads.add(record.payload_digest.removeprefix("sha256:"))
        # CAS orphans are non-authoritative and safe after a pre-commit crash.
        orphan_records = {p.stem for p in self.records.glob("*.json")} - referenced_records
        orphan_payloads = {p.stem for p in self.payloads.glob("*.json")} - referenced_payloads
        return {
            "ok": True,
            "records": len(events),
            "promotion_eligible": sum(bool(x.get("promotion_eligible")) for x in events),
            "head": events[-1]["hash"] if events else GENESIS,
            "orphan_records": len(orphan_records),
            "orphan_payloads": len(orphan_payloads),
        }


class TrustedEvidenceIngestor:
    """Narrow ingestion capability with explicit trust classes."""

    def __init__(self, ledger: EvidenceLedger, *, ingestor_id: str):
        if not str(ingestor_id).strip():
            raise ValueError("ingestor_id is required")
        self.ledger = ledger
        self.ingestor_id = str(ingestor_id)

    def ingest(
        self,
        payload: Any,
        *,
        origin_class: EvidenceOrigin,
        production_identity_digest: str,
        provenance: Mapping[str, Any],
        observed_at: float | None = None,
        valid_from: float | None = None,
        valid_until: float | None = None,
        confidence: float = 1.0,
        parent_digests: Sequence[str] = (),
        source_locator: str = "",
        summary: str = "",
    ) -> EvidenceRecord:
        if origin_class is EvidenceOrigin.SIMULATION:
            evidence_class = EvidenceClass.SIMULATED
        elif origin_class is EvidenceOrigin.MODEL_INFERENCE:
            evidence_class = EvidenceClass.INFERRED
        elif origin_class is EvidenceOrigin.GROUNDED_REPLAY:
            evidence_class = EvidenceClass.REPLAY
        else:
            evidence_class = EvidenceClass.OBSERVED
        record = EvidenceRecord(
            evidence_id="E-" + uuid.uuid4().hex,
            origin_class=origin_class,
            evidence_class=evidence_class,
            producer=self.ingestor_id,
            payload_digest=sha256_json(payload),
            provenance_digest=sha256_json(dict(provenance)),
            production_identity_digest=str(production_identity_digest),
            observed_at=float(time.time() if observed_at is None else observed_at),
            valid_from=None if valid_from is None else float(valid_from),
            valid_until=None if valid_until is None else float(valid_until),
            confidence=float(confidence),
            parent_digests=tuple(str(x) for x in parent_digests),
            source_locator=str(source_locator),
            summary=str(summary),
        )
        self.ledger._append_trusted(record, payload, capability=_INGEST_CAPABILITY, actor=self.ingestor_id)
        return record

    def ingest_verified_derivation(
        self,
        payload: Any,
        *,
        production_identity_digest: str,
        provenance: Mapping[str, Any],
        parent_digests: Sequence[str],
        verification_digest: str,
        confidence: float = 1.0,
        summary: str = "",
    ) -> EvidenceRecord:
        parents = tuple(str(x) for x in parent_digests)
        if not parents:
            raise ValueError("verified derivation requires parent evidence")
        if not str(verification_digest).startswith("sha256:"):
            raise ValueError("verification_digest must be sha256")
        for digest in parents:
            if not self.ledger.load(digest).promotion_eligible:
                raise PermissionError("verified derivation cannot inherit authority from non-authoritative evidence")
        record = EvidenceRecord(
            evidence_id="E-" + uuid.uuid4().hex,
            origin_class=EvidenceOrigin.DETERMINISTIC_TOOL,
            evidence_class=EvidenceClass.DERIVED_VERIFIED,
            producer=self.ingestor_id,
            payload_digest=sha256_json(payload),
            provenance_digest=sha256_json(dict(provenance)),
            production_identity_digest=str(production_identity_digest),
            observed_at=time.time(),
            confidence=float(confidence),
            parent_digests=parents,
            summary=str(summary),
            verification_digest=str(verification_digest),
        )
        self.ledger._append_trusted(record, payload, capability=_INGEST_CAPABILITY, actor=self.ingestor_id)
        return record
