from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import time
from typing import Any

from kvcontinual.execution.authority import Ed25519ReceiptSigner, Ed25519ReceiptVerifier
from kvcontinual.execution.digests import sha256_json
from kvcontinual.execution.governed_manifest import GovernedRuntimeManifest
from kvcontinual.execution.durability.control_state import ControlState
from kvcontinual.execution.durability.file_lock import ProcessFileLock


@dataclass(frozen=True)
class RuntimeTransition:
    transition_id: str
    kind: str
    nonce: str
    from_runtime_digest: str | None
    to_runtime_digest: str
    from_generation: int
    to_generation: int
    transition_sequence: int
    promotion_decision_digest: str
    previous_transition_digest: str | None
    reason: str

    def body(self) -> dict[str, Any]:
        return {
            "receipt_type": "rc11.runtime-transition.v1",
            **self.__dict__,
        }


class RuntimeManifestStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError("invalid manifest digest")
        return self.root / f"{digest[7:]}.json"

    def put(self, manifest: GovernedRuntimeManifest) -> str:
        manifest.validate()
        path = self.path_for(manifest.digest)
        payload = json.dumps(manifest.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        if path.exists():
            existing = GovernedRuntimeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if existing.digest != manifest.digest:
                raise RuntimeError("manifest store collision")
            return manifest.digest
        tmp = path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
        return manifest.digest

    def get(self, digest: str) -> GovernedRuntimeManifest:
        path = self.path_for(digest)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(digest)
        manifest = GovernedRuntimeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if manifest.digest != digest:
            raise RuntimeError("manifest content address mismatch")
        return manifest


class RuntimeActivationRegistry:
    """Fail-closed activation registry for exact signed RuntimeManifest transitions."""

    def __init__(self, root: str | Path, *, verifier: Ed25519ReceiptVerifier):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "activation.sqlite3"
        self.lock_path = self.root / "activation.lock"
        self.control = ControlState(self.root / "control.sqlite3")
        self.manifests = RuntimeManifestStore(self.root / "manifests")
        self.verifier = verifier
        self._init()

    def _connect(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        return c

    def _init(self) -> None:
        with self._connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS state(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                runtime_digest TEXT,
                generation INTEGER NOT NULL DEFAULT 0,
                transition_sequence INTEGER NOT NULL DEFAULT 0,
                transition_digest TEXT,
                updated_at REAL NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS transitions(
                transition_id TEXT PRIMARY KEY,
                nonce TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                sequence INTEGER NOT NULL UNIQUE,
                body_json TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                transition_digest TEXT NOT NULL UNIQUE,
                committed_at REAL NOT NULL)""")
            c.execute("INSERT OR IGNORE INTO state(singleton,generation,transition_sequence,updated_at) VALUES(1,0,0,?)", (time.time(),))
            c.commit()

    def state(self) -> dict[str, Any]:
        with self._connect() as c:
            r = c.execute("SELECT * FROM state WHERE singleton=1").fetchone()
        return dict(r)

    @staticmethod
    def transition_digest(body: dict[str, Any], receipt: dict[str, Any]) -> str:
        return sha256_json({"body": body, "authority_receipt": receipt})

    def activate(self, manifest_digest: str, receipt: dict[str, Any]) -> dict[str, Any]:
        manifest = self.manifests.get(manifest_digest)
        body = receipt.get("body") if isinstance(receipt, dict) else None
        if not isinstance(body, dict) or not self.verifier.verify(receipt):
            raise RuntimeError("invalid runtime transition authority receipt")
        if body.get("receipt_type") != "rc11.runtime-transition.v1":
            raise RuntimeError("wrong runtime transition receipt type")
        if body.get("to_runtime_digest") != manifest_digest:
            raise RuntimeError("authorization does not bind target runtime manifest")
        if body.get("promotion_decision_digest") != manifest.promotion_decision_digest:
            raise RuntimeError("authorization/promotion decision mismatch")
        kind = str(body.get("kind"))
        if kind not in {"promotion", "rollback"}:
            raise RuntimeError("invalid transition kind")

        with ProcessFileLock(self.lock_path, timeout=10.0):
            current = self.state()
            expected_from = current.get("runtime_digest")
            if body.get("from_runtime_digest") != expected_from:
                raise RuntimeError("runtime transition source mismatch")
            if int(body.get("from_generation", -1)) != int(current["generation"]):
                raise RuntimeError("runtime transition generation source mismatch")
            to_generation = int(body.get("to_generation", -1))
            if kind == "promotion" and to_generation <= int(current["generation"]):
                raise RuntimeError("promotion generation must increase")
            if kind == "rollback" and to_generation < 0:
                raise RuntimeError("rollback generation invalid")
            if manifest.generation != to_generation:
                raise RuntimeError("manifest generation does not match transition")
            if body.get("previous_transition_digest") != current.get("transition_digest"):
                raise RuntimeError("transition hash-chain predecessor mismatch")
            transaction_id = str(body.get("transition_id") or "")
            nonce = str(body.get("nonce") or "")
            if not transaction_id or not nonce:
                raise RuntimeError("transition id and nonce are required")
            seq = self.control.reserve(transaction_id=transaction_id, kind=kind, expected_generation=to_generation)
            if int(body.get("transition_sequence", -1)) != seq:
                self.control.update_phase(transaction_id, "aborted")
                record = self.control.record(transaction_id)
                if record is not None:
                    self.control.checkpoint(record)
                raise RuntimeError("transition sequence does not match global control sequence")
            if manifest.transition_sequence != seq:
                self.control.update_phase(transaction_id, "aborted")
                record = self.control.record(transaction_id)
                if record is not None:
                    self.control.checkpoint(record)
                raise RuntimeError("manifest transition sequence mismatch")
            td = self.transition_digest(body, receipt)
            try:
                with self._connect() as c:
                    c.execute("BEGIN IMMEDIATE")
                    c.execute("INSERT INTO transitions(transition_id,nonce,kind,sequence,body_json,receipt_json,transition_digest,committed_at) VALUES(?,?,?,?,?,?,?,?)",
                              (transaction_id, nonce, kind, seq, json.dumps(body, sort_keys=True, separators=(",", ":")),
                               json.dumps(receipt, sort_keys=True, separators=(",", ":")), td, time.time()))
                    c.execute("UPDATE state SET runtime_digest=?,generation=?,transition_sequence=?,transition_digest=?,updated_at=? WHERE singleton=1",
                              (manifest_digest, to_generation, seq, td, time.time()))
                    c.commit()
            except sqlite3.IntegrityError as exc:
                self.control.update_phase(transaction_id, "aborted")
                record = self.control.record(transaction_id)
                if record is not None:
                    self.control.checkpoint(record)
                raise RuntimeError("runtime transition replay or sequence collision") from exc
            self.control.update_phase(transaction_id, "committed")
            record = self.control.record(transaction_id)
            if record is None:
                raise RuntimeError("control-state mutation disappeared")
            self.control.checkpoint(record)
            return {"runtime_manifest_digest": manifest_digest, "transition_digest": td, "generation": to_generation, "sequence": seq}


def issue_runtime_transition(
    signer: Ed25519ReceiptSigner,
    *,
    transition_id: str,
    kind: str,
    nonce: str,
    from_runtime_digest: str | None,
    to_runtime_digest: str,
    from_generation: int,
    to_generation: int,
    transition_sequence: int,
    promotion_decision_digest: str,
    previous_transition_digest: str | None,
    reason: str,
) -> dict[str, Any]:
    transition = RuntimeTransition(
        transition_id=transition_id,
        kind=kind,
        nonce=nonce,
        from_runtime_digest=from_runtime_digest,
        to_runtime_digest=to_runtime_digest,
        from_generation=from_generation,
        to_generation=to_generation,
        transition_sequence=transition_sequence,
        promotion_decision_digest=promotion_decision_digest,
        previous_transition_digest=previous_transition_digest,
        reason=reason,
    )
    return signer.issue(transition.body())
