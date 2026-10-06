from __future__ import annotations

from dataclasses import replace

from kvcontinual.rc1025.cache.block import ArtifactQualification, ExecutionArtifact


def build_artifact_qualification(
    artifact: ExecutionArtifact,
    *,
    hardware_fingerprint: str,
    same_hidden_input_verified: bool,
    conv_boundary_complete: bool,
    attention_relocation_complete: bool,
    oracle_qualified: bool,
    max_logit_kl: float,
    min_top1_agreement: float,
    evidence_digest: str,
) -> ArtifactQualification:
    """Create a receipt bound to exact model identity and artifact bytes."""
    if not artifact.capture_manifest_digest:
        raise ValueError("artifact capture_manifest_digest is required before qualification")
    if not hardware_fingerprint:
        raise ValueError("hardware_fingerprint is required")
    if not evidence_digest:
        raise ValueError("evidence_digest is required")
    q = ArtifactQualification(
        same_hidden_input_verified=same_hidden_input_verified,
        conv_boundary_complete=conv_boundary_complete,
        attention_relocation_complete=attention_relocation_complete,
        oracle_qualified=oracle_qualified,
        max_logit_kl=float(max_logit_kl),
        min_top1_agreement=float(min_top1_agreement),
        hardware_fingerprint=hardware_fingerprint,
        capture_manifest_digest=artifact.capture_manifest_digest,
        execution_identity_digest=artifact.identity.digest,
        artifact_content_digest=artifact.content_digest,
        evidence_digest=evidence_digest,
    )
    return replace(q, receipt_digest=q.expected_receipt_digest())


def attach_qualification(artifact: ExecutionArtifact, qualification: ArtifactQualification) -> ExecutionArtifact:
    artifact.qualification = qualification
    artifact.validate()
    return artifact
