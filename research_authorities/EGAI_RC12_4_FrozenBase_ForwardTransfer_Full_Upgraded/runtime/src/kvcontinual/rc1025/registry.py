from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from kvcontinual.rc1025.digests import sha256_file, sha256_json
from kvcontinual.rc1025.hardware_qualification import HardwareQualificationStore
from kvcontinual.rc1025.deployment_binding import AccelerationDeploymentBinding
from kvcontinual.rc1025.types import ModelIdentity, QualificationRecord, PromotionDecision
from kvcontinual.rc1025.promotion_wal import PromotionWal, digest_json


@dataclass
class CandidateManifest:
    candidate_id: str
    base_model_digest: str
    parent_adapter_digest: str | None
    dataset_digest: str
    training_config_digest: str
    adapter_digest: str
    created_at: str


class AdapterRegistry:
    """Candidate registry with atomic model/cache namespace promotion metadata."""
    def __init__(self, root: str, hardware_qualification_store: HardwareQualificationStore | None = None):
        self.root = Path(root)
        self.hardware_qualification_store = hardware_qualification_store
        self.candidates = self.root / "candidates"
        self.promoted = self.root / "promoted"
        self.meta = self.root / "meta"
        self.namespaces = self.root / "cache_namespaces"
        for p in (self.candidates, self.promoted, self.meta, self.namespaces):
            p.mkdir(parents=True, exist_ok=True)
        self.promotion_wal = PromotionWal(self.meta / "promotion_wal.jsonl")

    def register_candidate(self, adapter_file: str, base_model_digest: str, dataset_digest: str, training_config: dict, parent_adapter_digest: str | None = None) -> CandidateManifest:
        cid = str(uuid.uuid4())
        dst_dir = self.candidates / cid; dst_dir.mkdir()
        dst = dst_dir / Path(adapter_file).name
        shutil.copy2(adapter_file, dst)
        manifest = CandidateManifest(cid, base_model_digest, parent_adapter_digest, dataset_digest, sha256_json(training_config), sha256_file(dst), datetime.now(timezone.utc).isoformat())
        (dst_dir / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True))
        return manifest

    def write_qualification(self, q: QualificationRecord) -> None:
        path = self.candidates / q.candidate_id / "qualification.json"
        if not path.parent.exists():
            raise FileNotFoundError(q.candidate_id)
        payload = asdict(q); payload["decision"] = q.decision.value
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def stage_cache_namespace(
        self,
        candidate_id: str,
        namespace_digest: str,
        warm_fraction: float = 0.0,
        *,
        accelerated: bool = False,
        hardware_qualification_certificate_digest: str = "",
        execution_identity_digest: str = "",
        backend_fingerprint: str = "",
        hardware_runtime_digest: str = "",
        release_manifest_digest: str = "",
        qualification_ledger_head: str | None = None,
        qualification_suite_digest: str | None = None,
        deployment_binding_digest: str | None = None,
    ) -> Path:
        if accelerated and not hardware_qualification_certificate_digest:
            raise ValueError("accelerated cache namespace requires hardware qualification certificate")
        if accelerated and not execution_identity_digest:
            raise ValueError("accelerated cache namespace requires execution identity digest")
        if accelerated and not backend_fingerprint:
            raise ValueError("accelerated cache namespace requires backend fingerprint")
        if accelerated and not hardware_runtime_digest:
            raise ValueError("accelerated cache namespace requires hardware runtime digest")
        if accelerated and not release_manifest_digest:
            raise ValueError("accelerated cache namespace requires release manifest digest")
        if hardware_qualification_certificate_digest and not hardware_qualification_certificate_digest.startswith("sha256:"):
            raise ValueError("hardware qualification certificate digest must be sha256")
        if accelerated:
            if self.hardware_qualification_store is None:
                raise RuntimeError("accelerated cache namespace requires configured hardware qualification store")
            certificate = self.hardware_qualification_store.get(hardware_qualification_certificate_digest)
            if certificate is None or not certificate.reusable:
                raise RuntimeError("hardware qualification certificate is missing or corrupt")
            if certificate.execution_identity_digest != execution_identity_digest:
                raise RuntimeError("hardware qualification certificate execution identity mismatch")
            try:
                # Full deployment-time binding. Runtime checks this again, but an
                # incompatible namespace must never be promoted in the first place.
                if certificate.backend_fingerprint != backend_fingerprint:
                    raise ValueError("backend fingerprint mismatch")
                if certificate.hardware_runtime_digest != hardware_runtime_digest:
                    raise ValueError("hardware runtime mismatch")
                if certificate.release_manifest_digest != release_manifest_digest:
                    raise ValueError("release manifest mismatch")
                if qualification_ledger_head is not None and certificate.qualification_ledger_head != qualification_ledger_head:
                    raise ValueError("qualification ledger head mismatch")
                if qualification_suite_digest is not None and certificate.qualification_suite_digest != qualification_suite_digest:
                    raise ValueError("qualification suite mismatch")
            except ValueError as exc:
                raise RuntimeError(f"hardware qualification deployment binding failed: {exc}") from exc
        p = self.namespaces / candidate_id
        p.mkdir(exist_ok=True)
        payload = {
            "candidate_id": candidate_id,
            "namespace_digest": namespace_digest,
            "warm_fraction": warm_fraction,
            "accelerated": bool(accelerated),
            "hardware_qualification_certificate_digest": hardware_qualification_certificate_digest,
            "execution_identity_digest": execution_identity_digest,
            "backend_fingerprint": backend_fingerprint,
            "hardware_runtime_digest": hardware_runtime_digest,
            "release_manifest_digest": release_manifest_digest,
            "qualification_ledger_head": qualification_ledger_head or "",
            "qualification_suite_digest": qualification_suite_digest or "",
            "deployment_binding_digest": deployment_binding_digest or "",
        }
        (p / "namespace.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
        return p

    def stage_accelerated_cache_namespace(
        self,
        candidate_id: str,
        namespace_digest: str,
        binding: AccelerationDeploymentBinding,
        warm_fraction: float = 0.0,
    ) -> Path:
        if not binding.reusable:
            raise ValueError("accelerated deployment binding is not reusable")
        if self.hardware_qualification_store is None:
            raise RuntimeError("accelerated cache namespace requires configured hardware qualification store")
        certificate=self.hardware_qualification_store.get(binding.certificate_digest)
        if certificate is None:
            raise RuntimeError("deployment binding certificate is missing or corrupt")
        binding.validate_certificate(certificate)
        return self.stage_cache_namespace(
            candidate_id, namespace_digest, warm_fraction,
            accelerated=True,
            hardware_qualification_certificate_digest=binding.certificate_digest,
            execution_identity_digest=binding.execution_identity_digest,
            backend_fingerprint=binding.backend_fingerprint,
            hardware_runtime_digest=binding.hardware_runtime_digest,
            release_manifest_digest=binding.release_manifest_digest,
            qualification_ledger_head=binding.qualification_ledger_head,
            qualification_suite_digest=binding.qualification_suite_digest,
            deployment_binding_digest=binding.binding_digest,
        )

    def _read_production_state(self) -> dict:
        p = self.meta / "production.json"
        if not p.exists():
            return {}
        raw = json.loads(p.read_text())
        if not isinstance(raw, dict):
            raise RuntimeError("production state must be a JSON object")
        return raw

    @staticmethod
    def _state_with_digest(state: dict) -> dict:
        state = dict(state)
        state.pop("state_digest", None)
        state["state_digest"] = digest_json(state)
        return state

    @staticmethod
    def _verify_state_digest(state: dict) -> None:
        if not state:
            return
        expected = state.get("state_digest", "")
        body = dict(state); body.pop("state_digest", None)
        if expected != digest_json(body):
            raise RuntimeError("production state digest mismatch")

    def promote(self, candidate_id: str) -> Path:
        qpath = self.candidates / candidate_id / "qualification.json"
        if not qpath.exists():
            raise RuntimeError("Candidate has no qualification record")
        q = json.loads(qpath.read_text())
        if q["decision"] != PromotionDecision.PROMOTE.value:
            raise RuntimeError("Candidate is not qualified for promotion")
        nspath = self.namespaces / candidate_id / "namespace.json"
        if not nspath.exists():
            raise RuntimeError("Candidate cache namespace is not staged")
        ns = json.loads(nspath.read_text())
        if ns.get("accelerated"):
            cert_digest = ns.get("hardware_qualification_certificate_digest", "")
            if not cert_digest:
                raise RuntimeError("Accelerated candidate cache namespace lacks hardware qualification certificate")
            if self.hardware_qualification_store is None:
                raise RuntimeError("Accelerated promotion requires configured hardware qualification store")
            certificate = self.hardware_qualification_store.get(cert_digest)
            if certificate is None or not certificate.reusable:
                raise RuntimeError("Accelerated promotion hardware qualification certificate is missing or corrupt")
            if certificate.execution_identity_digest != ns.get("execution_identity_digest"):
                raise RuntimeError("Accelerated promotion hardware qualification identity mismatch")
            checks = {
                "backend fingerprint": (certificate.backend_fingerprint, ns.get("backend_fingerprint")),
                "hardware runtime": (certificate.hardware_runtime_digest, ns.get("hardware_runtime_digest")),
                "release manifest": (certificate.release_manifest_digest, ns.get("release_manifest_digest")),
            }
            if ns.get("qualification_ledger_head"):
                checks["qualification ledger"] = (certificate.qualification_ledger_head, ns.get("qualification_ledger_head"))
            if ns.get("qualification_suite_digest"):
                checks["qualification suite"] = (certificate.qualification_suite_digest, ns.get("qualification_suite_digest"))
            for label, (actual, expected) in checks.items():
                if actual != expected:
                    raise RuntimeError(f"Accelerated promotion hardware qualification {label} mismatch")

        src = self.candidates / candidate_id
        dst = self.promoted / candidate_id
        before = self._read_production_state()
        if before:
            self._verify_state_digest(before)
        # Idempotent retry: do not create another generation/WAL transaction.
        if before.get("current") == candidate_id and before.get("cache_namespace") == ns:
            self.audit_production_state()
            return dst

        previous = before.get("current")
        generation = int(before.get("generation", 0)) + 1
        after = self._state_with_digest({
            "current": candidate_id,
            "previous": previous,
            "cache_namespace": ns,
            "generation": generation,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        prepare = self.promotion_wal.prepare(action="PROMOTE", candidate_id=candidate_id, before_state=before, after_state=after)
        try:
            if dst.exists(): shutil.rmtree(dst)
            tmp_dst = self.promoted / f".{candidate_id}.tmp-{prepare.tx_id}"
            if tmp_dst.exists(): shutil.rmtree(tmp_dst)
            shutil.copytree(src, tmp_dst)
            tmp_dst.replace(dst)
            self._atomic_json(self.meta / "production.json", after)
            self.promotion_wal.commit(prepare, after)
        except Exception as exc:
            try:
                if before:
                    self._atomic_json(self.meta / "production.json", before)
                else:
                    (self.meta / "production.json").unlink(missing_ok=True)
                self.promotion_wal.abort(prepare, f"promotion failed: {exc}")
            finally:
                raise
        return dst

    def current_id(self) -> str | None:
        state = self._read_production_state()
        if state:
            self._verify_state_digest(state)
        return state.get("current") or None

    def rollback(self) -> str:
        before = self._read_production_state()
        if not before:
            raise RuntimeError("No production state")
        self._verify_state_digest(before)
        prev = before.get("previous")
        if not prev:
            raise RuntimeError("No previous promoted adapter to roll back to")
        current = before.get("current")
        prev_ns = self.namespaces / prev / "namespace.json"
        if not prev_ns.exists():
            raise RuntimeError("Previous cache namespace is unavailable")
        after = self._state_with_digest({
            "current": prev,
            "previous": current,
            "cache_namespace": json.loads(prev_ns.read_text()),
            "generation": int(before.get("generation", 0)) + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        prepare = self.promotion_wal.prepare(action="ROLLBACK", candidate_id=prev, before_state=before, after_state=after)
        try:
            self._atomic_json(self.meta / "production.json", after)
            self.promotion_wal.commit(prepare, after)
        except Exception as exc:
            try:
                self._atomic_json(self.meta / "production.json", before)
                self.promotion_wal.abort(prepare, f"rollback failed: {exc}")
            finally:
                raise
        return prev

    def audit_production_state(self) -> dict:
        state = self._read_production_state()
        if state:
            self._verify_state_digest(state)
        self.promotion_wal.audit_installed_state(state)
        return state

    def recover_production_state(self) -> dict:
        pending = self.promotion_wal.pending()
        state = self._read_production_state()
        if not pending:
            self.audit_production_state()
            return state
        if len(pending) != 1:
            raise RuntimeError("multiple unresolved deployment transactions require manual intervention")
        prepare = pending[0]
        before = dict(prepare.payload["before_state"])
        after = dict(prepare.payload["after_state"])
        # Fail safe: never assume an uncommitted new production pointer is valid.
        if state == after or state == before or not state:
            if before:
                self._atomic_json(self.meta / "production.json", before)
            else:
                (self.meta / "production.json").unlink(missing_ok=True)
            self.promotion_wal.abort(prepare, "startup recovery rolled back uncommitted transition")
            return before
        raise RuntimeError("production state does not match unresolved WAL transition; manual intervention required")

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        PromotionWal.atomic_write_json(path, payload)
