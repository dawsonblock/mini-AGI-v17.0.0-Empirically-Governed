from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from kvcontinual.rc1025.cache.store import ExecutionArtifactStore
from kvcontinual.rc1025.checkpoints import PrefixCheckpointStore
from kvcontinual.rc1025.hybrid.seam_plan import build_seam_first_plan
from kvcontinual.rc1025.hybrid.execution_receipt import validate_seam_execution_receipt
from kvcontinual.rc1025.hybrid.tail_injection import validate_tail_injection_receipt
from kvcontinual.rc1025.hardware_qualification import HardwareQualificationStore
from kvcontinual.rc1025.recurrent.coherence import RuntimeRiskGate
from kvcontinual.rc1025.recurrent.interfaces import ReconstructionBackend, backend_capabilities
from kvcontinual.rc1025.source import SourceSegmentStore
from kvcontinual.rc1025.types import AssemblyTopology, ExecutionIdentity, OracleMetrics, ReconstructionAction, ReconstructionMode, RuntimeRiskSignals


@dataclass
class ReconstructionResult:
    action: ReconstructionAction
    state: Any
    topology: AssemblyTopology
    risk_signals: RuntimeRiskSignals | None = None
    shadow_oracle_metrics: OracleMetrics | None = None
    cache_misses: list[str] | None = None
    reason: str = ""


class ShadowAuditSampler:
    def __init__(self, rate: float = 0.01, salt: str = "rc10"):
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be in [0,1]")
        self.rate = rate
        self.salt = salt

    def selected(self, request_key: str) -> bool:
        if self.rate <= 0:
            return False
        h = hashlib.sha256((self.salt + request_key).encode()).digest()
        u = int.from_bytes(h[:8], "big") / float(2**64)
        return u < self.rate


class ReconstructionRuntime:
    """Topology-aware RC10 reconstruction policy.

    Arbitrary PIC: fixed seam-8 HYPIC first, then optional LinearKV baseline,
    then exact selected replay. Prefix-only reconstruction is never used as a
    generic arbitrary-segment fallback.
    """
    def __init__(
        self,
        source_store: SourceSegmentStore,
        artifact_store: ExecutionArtifactStore,
        backend: ReconstructionBackend,
        checkpoints: PrefixCheckpointStore | None = None,
        gate: RuntimeRiskGate | None = None,
        shadow_sampler: ShadowAuditSampler | None = None,
        allow_single_state_experimental: bool = False,
        hardware_qualification_store: HardwareQualificationStore | None = None,
        hardware_runtime_digest: str = "",
        release_manifest_digest: str = "",
        qualification_ledger_head: str | None = None,
    ):
        self.source_store = source_store
        self.artifact_store = artifact_store
        self.backend = backend
        self.checkpoints = checkpoints or PrefixCheckpointStore()
        self.gate = gate or RuntimeRiskGate()
        self.shadow_sampler = shadow_sampler or ShadowAuditSampler(0.0)
        self.allow_single_state_experimental = allow_single_state_experimental
        self.hardware_qualification_store = hardware_qualification_store
        self.hardware_runtime_digest = hardware_runtime_digest
        self.release_manifest_digest = release_manifest_digest
        self.qualification_ledger_head = qualification_ledger_head

    def _validate_source_bindings(self, source_segment_ids: list[str], artifacts: list[Any]) -> tuple[bool, str]:
        """Verify every derived artifact was compiled from the current immutable source bytes."""
        if len(source_segment_ids) != len(artifacts):
            return False, "artifact/source cardinality mismatch"
        for sid, art in zip(source_segment_ids, artifacts):
            if art.source_segment_id != sid:
                return False, f"artifact order/source mismatch for {sid}"
            expected = self.source_store.token_digest(sid)
            if expected is None:
                return False, f"authoritative source segment missing: {sid}"
            if not getattr(art, "source_token_digest", ""):
                return False, f"artifact lacks RC10.21 source-token binding: {sid}"
            if art.source_token_digest != expected:
                return False, f"artifact source-token digest mismatch: {sid}"
        return True, ""

    def reconstruct(
        self,
        source_segment_ids: list[str],
        identity: ExecutionIdentity,
        mode: ReconstructionMode = ReconstructionMode.BALANCED,
        *,
        topology: AssemblyTopology | None = None,
        conversation_id: str | None = None,
        target_token_position: int | None = None,
        request_key: str = "",
    ) -> ReconstructionResult:
        if not source_segment_ids:
            raise ValueError("source_segment_ids cannot be empty")
        topology = topology or self.source_store.classify_topology(source_segment_ids)
        caps = backend_capabilities(self.backend)

        if mode == ReconstructionMode.EXACT:
            return self._exact(source_segment_ids, topology, "EXACT mode requested")

        if topology in (AssemblyTopology.CANONICAL, AssemblyTopology.EXACT_PREFIX):
            if not caps.exact_prefix_checkpoint:
                return self._exact(source_segment_ids, topology, "backend has no exact prefix-checkpoint restore; replayed selected tokens")
            checkpoint = None
            checkpoint_reason = "shared/canonical prefix path"
            if conversation_id is not None and target_token_position is not None:
                checkpoint = self.checkpoints.deepest(conversation_id, target_token_position, identity)
                if checkpoint is not None:
                    try:
                        expected_prefix_digest = self.source_store.prefix_token_digest(source_segment_ids, checkpoint.token_position)
                    except (KeyError, ValueError):
                        checkpoint = None
                        checkpoint_reason = "prefix checkpoint range invalid; replayed selected prefix"
                    else:
                        if checkpoint.prefix_token_digest != expected_prefix_digest:
                            checkpoint = None
                            checkpoint_reason = "prefix checkpoint source digest mismatch; replayed selected prefix"
            state = self.backend.exact_prefix_replay(source_segment_ids, checkpoint)
            return ReconstructionResult(ReconstructionAction.EXACT_PREFIX_REPLAY, state, topology, reason=checkpoint_reason)

        if not caps.hypic_seam8:
            return self._exact(source_segment_ids, topology, "backend does not provide qualified HYPIC seam-8 artifacts")
        if not caps.causal_conv_seam_repair:
            return self._exact(source_segment_ids, topology, "backend lacks causal-convolution seam repair")
        if not caps.seam_first_execution:
            return self._exact(source_segment_ids, topology, "backend does not guarantee seam-first execution")
        if not caps.full_attention_relocation:
            return self._exact(source_segment_ids, topology, "backend lacks full-attention position relocation")

        hits, misses = self.artifact_store.resolve(source_segment_ids, identity)
        if misses:
            # Regenerate only from authoritative source tokens. A backend may cache
            # the resulting artifacts under this exact execution namespace.
            built = self.backend.materialize(misses, identity)
            for art in built:
                self.artifact_store.put(art)
            hits, still_missing = self.artifact_store.resolve(source_segment_ids, identity)
            if still_missing:
                return self._exact(source_segment_ids, topology, "cache materialization incomplete", still_missing)

        artifacts = [self.artifact_store.get(sid, identity) for sid in source_segment_ids]
        if any(a is None for a in artifacts):
            return self._exact(source_segment_ids, topology, "exact identity cache miss")
        artifacts = [a for a in artifacts if a is not None]

        bound, binding_reason = self._validate_source_bindings(source_segment_ids, artifacts)
        if not bound:
            return self._exact(source_segment_ids, topology, binding_reason)

        # Arbitrary assembly requires a seam contract that matches the cached tail.
        if any(a.fixed_seam_width != 8 for a in artifacts):
            return self._exact(source_segment_ids, topology, "arbitrary PIC requires fixed seam-8 artifact contract")
        if caps.requires_artifact_qualification and any(not a.hypic_qualified for a in artifacts):
            return self._exact(source_segment_ids, topology, "execution artifact lacks a complete HYPIC qualification receipt")
        if not caps.seam_trace_verification:
            return self._exact(source_segment_ids, topology, "backend does not provide verifiable seam execution traces")
        if not caps.execution_receipts or not caps.backend_fingerprint:
            return self._exact(source_segment_ids, topology, "backend does not provide bound seam execution receipts")
        if not caps.tail_injection_receipts:
            return self._exact(source_segment_ids, topology, "backend does not provide auditable cached-tail state-plane receipts")
        if caps.requires_hardware_qualification:
            if not caps.hardware_qualification_certificate_digest:
                return self._exact(source_segment_ids, topology, "accelerated backend has no hardware qualification certificate digest")
            if self.hardware_qualification_store is None:
                return self._exact(source_segment_ids, topology, "runtime has no hardware qualification store")
            if not self.hardware_runtime_digest or not self.release_manifest_digest:
                return self._exact(source_segment_ids, topology, "runtime lacks host/release qualification identity")
            certificate = self.hardware_qualification_store.get(caps.hardware_qualification_certificate_digest)
            if certificate is None:
                return self._exact(source_segment_ids, topology, "hardware qualification certificate missing or corrupt")
            try:
                certificate.validate(
                    identity=identity,
                    backend_fingerprint=caps.backend_fingerprint,
                    hardware_runtime_digest=self.hardware_runtime_digest,
                    release_manifest_digest=self.release_manifest_digest,
                    qualification_ledger_head=self.qualification_ledger_head,
                )
            except ValueError as exc:
                return self._exact(source_segment_ids, topology, f"hardware qualification rejected accelerated backend: {exc}")

        try:
            plan = build_seam_first_plan(self.source_store, source_segment_ids, artifacts, seam_width=8)
        except (ValueError, KeyError) as exc:
            return self._exact(source_segment_ids, topology, f"cannot build seam-first execution plan: {exc}")

        planned = getattr(self.backend, "hypic_seam8_with_plan", None)
        if planned is None:
            return self._exact(source_segment_ids, topology, "backend advertises seam-first execution but exposes no plan-aware HYPIC entrypoint")
        approx = planned(artifacts, plan)
        approx.metadata.setdefault("seam_plan_digest", plan.digest)
        if approx.trace is None:
            return self._exact(source_segment_ids, topology, "accelerated backend returned no seam execution trace")
        try:
            approx.trace.validate_against(plan)
        except ValueError as exc:
            return self._exact(source_segment_ids, topology, f"invalid seam execution trace: {exc}")
        if approx.execution_receipt is None:
            return self._exact(source_segment_ids, topology, "accelerated backend returned no seam execution receipt")
        try:
            validate_seam_execution_receipt(
                approx.execution_receipt, plan, artifacts, approx.trace,
                backend_fingerprint=caps.backend_fingerprint,
            )
        except ValueError as exc:
            return self._exact(source_segment_ids, topology, f"invalid seam execution receipt: {exc}")
        approx.metadata.setdefault("seam_trace_digest", approx.trace.digest)
        approx.metadata.setdefault("seam_execution_receipt_digest", approx.execution_receipt.receipt_digest)
        receipts = approx.tail_injection_receipts
        if receipts is None or len(receipts) != len(plan.steps):
            return self._exact(source_segment_ids, topology, "accelerated backend returned incomplete cached-tail injection receipts")
        for receipt, art, step in zip(receipts, artifacts, plan.steps):
            try:
                validate_tail_injection_receipt(receipt, art, step)
            except ValueError as exc:
                return self._exact(source_segment_ids, topology, f"invalid cached-tail injection receipt: {exc}")
        if not approx.state_plane_digest:
            return self._exact(source_segment_ids, topology, "accelerated backend returned no final state-plane digest")
        if receipts and approx.state_plane_digest != receipts[-1].after_state_digest:
            return self._exact(source_segment_ids, topology, "accelerated backend final state-plane digest does not match tail receipt")
        approx.metadata.setdefault("tail_injection_receipt_digests", [r.receipt_digest for r in receipts])
        approx.metadata.setdefault("final_state_plane_digest", approx.state_plane_digest)
        if mode == ReconstructionMode.FAST or self.gate.acceptable(approx.risk_signals):
            result = ReconstructionResult(
                ReconstructionAction.HYPIC_SEAM8,
                approx.state,
                topology,
                risk_signals=approx.risk_signals,
                reason="fixed seam-8 HYPIC path accepted",
            )
            self._maybe_shadow(result, source_segment_ids, request_key)
            return result

        if self.allow_single_state_experimental and caps.single_state_init:
            alt = self.backend.single_state_init(artifacts)
            if self.gate.acceptable(alt.risk_signals):
                result = ReconstructionResult(
                    ReconstructionAction.SINGLE_STATE_INIT,
                    alt.state,
                    topology,
                    risk_signals=alt.risk_signals,
                    reason="HYPIC seam risk high; LinearKV-style baseline accepted",
                )
                self._maybe_shadow(result, source_segment_ids, request_key)
                return result

        return self._exact(source_segment_ids, topology, "accelerated arbitrary-PIC path failed risk gate")

    def _exact(self, ids: list[str], topology: AssemblyTopology, reason: str, misses: list[str] | None = None):
        return ReconstructionResult(
            ReconstructionAction.EXACT_SELECTED_REPLAY,
            self.backend.exact_selected_replay(ids),
            topology,
            cache_misses=misses,
            reason=reason,
        )

    def _maybe_shadow(self, result: ReconstructionResult, ids: list[str], request_key: str) -> None:
        if self.shadow_sampler.selected(request_key or "|".join(ids)):
            exact = self.backend.exact_selected_replay(ids)
            result.shadow_oracle_metrics = self.backend.compare_to_oracle(result.state, exact)
