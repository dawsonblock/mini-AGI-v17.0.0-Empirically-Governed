from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable

from kvcontinual.rc1025.cache.block import ExecutionArtifact
from kvcontinual.rc1025.hybrid.seam_execution import SeamExecutionTrace
from kvcontinual.rc1025.hybrid.seam_plan import SeamFirstAssemblyPlan


def _digest_payload(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SeamExecutionReceipt:
    """Tamper-evident proof for one accelerated seam-first assembly.

    The receipt does not claim model-level exactness. It proves that a named
    backend executed the exact RC10 seam plan over the exact qualified artifacts
    under one ExecutionIdentity. Oracle quality remains a separate qualification
    property.
    """

    plan_digest: str
    execution_identity_digest: str
    artifact_content_digests: tuple[str, ...]
    trace_digest: str
    backend_fingerprint: str
    created_at: str
    receipt_digest: str = ""

    def unsigned_payload(self) -> dict:
        return {
            "plan_digest": self.plan_digest,
            "execution_identity_digest": self.execution_identity_digest,
            "artifact_content_digests": list(self.artifact_content_digests),
            "trace_digest": self.trace_digest,
            "backend_fingerprint": self.backend_fingerprint,
            "created_at": self.created_at,
        }

    def expected_digest(self) -> str:
        return _digest_payload(self.unsigned_payload())

    @property
    def valid_digest(self) -> bool:
        return bool(self.receipt_digest) and self.receipt_digest == self.expected_digest()


def build_seam_execution_receipt(
    plan: SeamFirstAssemblyPlan,
    artifacts: Iterable[ExecutionArtifact],
    trace: SeamExecutionTrace,
    *,
    backend_fingerprint: str,
) -> SeamExecutionReceipt:
    artifacts = tuple(artifacts)
    if not backend_fingerprint:
        raise ValueError("backend_fingerprint is required")
    plan.validate()
    trace.validate_against(plan)
    if len(artifacts) != len(plan.steps):
        raise ValueError("artifact count does not match seam plan")
    identity_digests = {a.identity.digest for a in artifacts}
    if len(identity_digests) != 1:
        raise ValueError("mixed execution identities cannot share a seam receipt")
    artifact_digests = tuple(a.content_digest for a in artifacts)
    if artifact_digests != tuple(step.artifact_content_digest for step in plan.steps):
        raise ValueError("artifact content does not match seam plan")
    identity_digest = next(iter(identity_digests))
    if any(step.execution_identity_digest != identity_digest for step in plan.steps):
        raise ValueError("execution identity does not match seam plan")
    r = SeamExecutionReceipt(
        plan_digest=plan.digest,
        execution_identity_digest=identity_digest,
        artifact_content_digests=artifact_digests,
        trace_digest=trace.digest,
        backend_fingerprint=backend_fingerprint,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return replace(r, receipt_digest=r.expected_digest())


def validate_seam_execution_receipt(
    receipt: SeamExecutionReceipt,
    plan: SeamFirstAssemblyPlan,
    artifacts: Iterable[ExecutionArtifact],
    trace: SeamExecutionTrace,
    *,
    backend_fingerprint: str,
) -> None:
    artifacts = tuple(artifacts)
    if not receipt.valid_digest:
        raise ValueError("seam execution receipt digest is invalid")
    if receipt.backend_fingerprint != backend_fingerprint:
        raise ValueError("seam execution receipt backend fingerprint mismatch")
    if receipt.plan_digest != plan.digest:
        raise ValueError("seam execution receipt plan digest mismatch")
    if receipt.trace_digest != trace.digest:
        raise ValueError("seam execution receipt trace digest mismatch")
    if receipt.artifact_content_digests != tuple(a.content_digest for a in artifacts):
        raise ValueError("seam execution receipt artifact digest mismatch")
    ids = {a.identity.digest for a in artifacts}
    if len(ids) != 1 or receipt.execution_identity_digest != next(iter(ids)):
        raise ValueError("seam execution receipt execution identity mismatch")
    trace.validate_against(plan)
