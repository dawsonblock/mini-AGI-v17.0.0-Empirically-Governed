"""Canonical RC13.3 assembly: governed learning over transactional execution state."""
from pathlib import Path

from kvcontinual.execution.source import SourceSegmentStore
from kvcontinual.execution.cache.persistent import PersistentExecutionArtifactStore
from kvcontinual.execution.runtime import ReconstructionRuntime
from kvcontinual.execution.types import ReconstructionMode
from kvcontinual.execution.qualification_bundle import verify_qualification_bundle
from kvcontinual.execution.macos_qualification_preflight import run_macos_qualification_preflight
from kvcontinual.execution.hardware_qualification import detect_hardware_runtime_fingerprint
from kvcontinual.execution.activation import RuntimeActivationRegistry
from minagi.egai import (
    EvidenceLedger, SkillRepository, BeliefRepository,
    CognitivePlane, LearningPlane, PromotionAuthority,
    ImprovementLedger, IndependentQualificationGate,
)
from minagi.egai.canonical import sha256_json
from minagi.state_epoch import StateEpoch, StateEpochRegistry


class GovernedSystem:
    """Canonical converged runtime.

    Research qualification, deployment activation, and StateEpoch activation are
    separate authority transitions. Fast execution remains disabled unless target
    qualification is bound. If an active StateEpoch exists, every request checks
    that it still binds the active runtime manifest before allowing acceleration.
    """

    def __init__(
        self,
        root,
        backend,
        *,
        research_verifier,
        promotion_signer,
        budget=None,
        runtime_transition_verifier=None,
        state_epoch_verifier=None,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.sources = SourceSegmentStore(str(self.root / "source.sqlite3"))
        self.artifacts = PersistentExecutionArtifactStore(self.root / "execution", budget=budget)
        self.execution = ReconstructionRuntime(self.sources, self.artifacts, backend)
        self.evidence = EvidenceLedger(self.root / "evidence")
        self.skills = SkillRepository(self.root / "skills")
        self.beliefs = BeliefRepository(self.root / "beliefs")
        self.cognitive = CognitivePlane(evidence=self.evidence, skills=self.skills, beliefs=self.beliefs)
        self.learning = LearningPlane(skills=self.skills, beliefs=self.beliefs)
        self.promotion = PromotionAuthority(
            gate=IndependentQualificationGate(chain_verifier=research_verifier),
            improvement_ledger=ImprovementLedger(self.root / "improvements"),
            signer=promotion_signer,
        )
        default_verifier = promotion_signer.verifier() if hasattr(promotion_signer, "verifier") else None
        rv = runtime_transition_verifier or default_verifier
        sv = state_epoch_verifier or default_verifier
        if rv is None or sv is None:
            raise ValueError("runtime/state transition verifiers are required")
        self.runtime_activation = RuntimeActivationRegistry(self.root / "runtime_activation", verifier=rv)
        self.state_epochs = StateEpochRegistry(self.root / "state_epochs", verifier=sv)
        self._qualification = None

    def bind_target_qualification(
        self,
        *,
        identity,
        bundle,
        receipt,
        verifier,
        certificate,
        deployment_binding,
        backend_fingerprint,
        release_manifest_digest,
        qualification_ledger_head,
        qualification_suite_digest,
    ):
        preflight = run_macos_qualification_preflight(backend_fingerprint=backend_fingerprint)
        preflight.validate()
        if bundle.get("schema_version") != 2 or not verify_qualification_bundle(bundle):
            raise PermissionError("valid content-bound execution qualification required")
        if bundle["execution_identity_digest"] != identity.digest or bundle["runtime_build_digest"] != release_manifest_digest:
            raise PermissionError("qualification execution/release identity mismatch")
        hardware = detect_hardware_runtime_fingerprint(backend_fingerprint=backend_fingerprint)
        certificate.validate(
            identity=identity,
            backend_fingerprint=backend_fingerprint,
            hardware_runtime_digest=hardware.digest,
            release_manifest_digest=release_manifest_digest,
            qualification_suite_digest=qualification_suite_digest,
            qualification_ledger_head=qualification_ledger_head,
        )
        deployment_binding.validate_certificate(certificate)
        signed_body = {
            "schema": "mini-agi-target-deployment-v1",
            "bundle": bundle,
            "certificate_digest": certificate.certificate_digest,
            "deployment_binding_digest": deployment_binding.binding_digest,
            "hardware_runtime_digest": hardware.digest,
        }
        if not verifier.verify(receipt, expected_body=signed_body):
            raise PermissionError("independent execution/deployment qualification signature required")
        self._qualification = (
            identity.digest, backend_fingerprint, release_manifest_digest,
            signed_body, receipt, verifier, hardware.digest,
        )

    def prepare_state_epoch(
        self,
        *,
        epoch: int,
        foundation_model_digest: str,
        tokenizer_digest: str,
        memory_policy_digest: str,
        retrieval_policy_digest: str,
        promotion_decision_digest: str,
        adapter_digests=(),
    ) -> StateEpoch:
        runtime_state = self.runtime_activation.state()
        runtime_digest = runtime_state.get("runtime_digest")
        if not runtime_digest:
            raise RuntimeError("cannot prepare StateEpoch without an active governed runtime manifest")
        current = self.state_epochs.active()
        obj = StateEpoch.create(
            epoch=epoch,
            predecessor_digest=None if current is None else current.digest,
            foundation_model_digest=foundation_model_digest,
            tokenizer_digest=tokenizer_digest,
            runtime_manifest_digest=str(runtime_digest),
            belief_snapshot_digest=self.beliefs.snapshot_digest,
            skill_snapshot_digest=self.skills.snapshot_digest,
            memory_policy_digest=memory_policy_digest,
            retrieval_policy_digest=retrieval_policy_digest,
            adapter_set_digest=sha256_json(sorted(str(x) for x in adapter_digests)),
            promotion_decision_digest=promotion_decision_digest,
        )
        self.state_epochs.prepare(obj)
        return obj

    def reconstruct(self, segment_ids, identity, mode=ReconstructionMode.EXACT, **kwargs):
        q = self._qualification
        active_epoch = self.state_epochs.active()
        if active_epoch is not None:
            runtime_state = self.runtime_activation.state()
            if runtime_state.get("runtime_digest") != active_epoch.runtime_manifest_digest:
                # Mixed-generation state is a correctness failure; never accelerate it.
                mode = ReconstructionMode.EXACT
        if q is None or q[0] != identity.digest:
            mode = ReconstructionMode.EXACT
        else:
            hardware = detect_hardware_runtime_fingerprint(backend_fingerprint=q[1])
            if hardware.digest != q[6] or not q[5].verify(q[4], expected_body=q[3]):
                self._qualification = None
                mode = ReconstructionMode.EXACT
        return self.execution.reconstruct(segment_ids, identity, mode, **kwargs)

    def verify_control_plane(self):
        return {
            "evidence": self.evidence.verify(),
            "skills": self.skills.verify(),
            "beliefs": self.beliefs.verify(),
            "improvements": self.promotion.improvement_ledger.verify(),
            "runtime_activation": self.runtime_activation.control.integrity_check(),
            "state_epochs": self.state_epochs.verify(),
        }

    def close(self):
        self.artifacts.close()
        self.sources.conn.close()
