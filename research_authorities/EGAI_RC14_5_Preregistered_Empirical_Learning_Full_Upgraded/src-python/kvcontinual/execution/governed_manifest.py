from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable

from kvcontinual.execution.digests import sha256_json


def _is_digest(value: str) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value) == 71


def _require_digest(name: str, value: str) -> None:
    if not _is_digest(value):
        raise ValueError(f"{name} must be a sha256: digest")


@dataclass(frozen=True)
class GovernedRuntimeManifest:
    """Exact executable closure authorized by the promotion plane.

    The manifest deliberately binds learning artifacts, execution implementation,
    qualification evidence and platform qualification in one content-addressed
    object. Deployment accepts the manifest digest, not a loose set of runtime
    parameters that could be substituted after qualification.
    """

    schema_version: int
    runtime_id: str
    generation: int
    transition_sequence: int
    foundation_model_digest: str
    tokenizer_digest: str
    execution_engine_digest: str
    execution_config_digest: str
    kvmem_implementation_digest: str
    gdn_implementation_digest: str
    attention_implementation_digest: str
    adapter_digests: tuple[str, ...] = field(default_factory=tuple)
    skill_digests: tuple[str, ...] = field(default_factory=tuple)
    memory_policy_digest: str = ""
    candidate_digest: str = ""
    build_manifest_digest: str = ""
    evaluation_bundle_digest: str = ""
    qualification_record_digest: str = ""
    promotion_decision_digest: str = ""
    platform_qualification_digest: str = ""
    created_at: str = ""

    @classmethod
    def create(
        cls,
        *,
        runtime_id: str,
        generation: int,
        transition_sequence: int,
        foundation_model_digest: str,
        tokenizer_digest: str,
        execution_engine_digest: str,
        execution_config_digest: str,
        kvmem_implementation_digest: str,
        gdn_implementation_digest: str,
        attention_implementation_digest: str,
        adapter_digests: Iterable[str] = (),
        skill_digests: Iterable[str] = (),
        memory_policy_digest: str,
        candidate_digest: str,
        build_manifest_digest: str,
        evaluation_bundle_digest: str,
        qualification_record_digest: str,
        promotion_decision_digest: str,
        platform_qualification_digest: str,
    ) -> "GovernedRuntimeManifest":
        m = cls(
            schema_version=2,
            runtime_id=runtime_id,
            generation=int(generation),
            transition_sequence=int(transition_sequence),
            foundation_model_digest=foundation_model_digest,
            tokenizer_digest=tokenizer_digest,
            execution_engine_digest=execution_engine_digest,
            execution_config_digest=execution_config_digest,
            kvmem_implementation_digest=kvmem_implementation_digest,
            gdn_implementation_digest=gdn_implementation_digest,
            attention_implementation_digest=attention_implementation_digest,
            adapter_digests=tuple(adapter_digests),
            skill_digests=tuple(skill_digests),
            memory_policy_digest=memory_policy_digest,
            candidate_digest=candidate_digest,
            build_manifest_digest=build_manifest_digest,
            evaluation_bundle_digest=evaluation_bundle_digest,
            qualification_record_digest=qualification_record_digest,
            promotion_decision_digest=promotion_decision_digest,
            platform_qualification_digest=platform_qualification_digest,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        m.validate()
        return m

    def validate(self) -> None:
        if self.schema_version != 2:
            raise ValueError("unsupported governed runtime manifest schema")
        if not self.runtime_id or len(self.runtime_id) > 256:
            raise ValueError("invalid runtime_id")
        if self.generation < 0 or self.transition_sequence < 0:
            raise ValueError("generation/transition_sequence cannot be negative")
        required = {
            "foundation_model_digest": self.foundation_model_digest,
            "tokenizer_digest": self.tokenizer_digest,
            "execution_engine_digest": self.execution_engine_digest,
            "execution_config_digest": self.execution_config_digest,
            "kvmem_implementation_digest": self.kvmem_implementation_digest,
            "gdn_implementation_digest": self.gdn_implementation_digest,
            "attention_implementation_digest": self.attention_implementation_digest,
            "memory_policy_digest": self.memory_policy_digest,
            "candidate_digest": self.candidate_digest,
            "build_manifest_digest": self.build_manifest_digest,
            "evaluation_bundle_digest": self.evaluation_bundle_digest,
            "qualification_record_digest": self.qualification_record_digest,
            "promotion_decision_digest": self.promotion_decision_digest,
            "platform_qualification_digest": self.platform_qualification_digest,
        }
        for name, value in required.items():
            _require_digest(name, value)
        for name, seq in (("adapter_digests", self.adapter_digests), ("skill_digests", self.skill_digests)):
            if len(seq) != len(set(seq)):
                raise ValueError(f"duplicate entries in {name}")
            for value in seq:
                _require_digest(name, value)
        if not self.created_at:
            raise ValueError("created_at is required")

    def payload(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @property
    def digest(self) -> str:
        return sha256_json(self.payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "manifest_digest": self.digest}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GovernedRuntimeManifest":
        expected = str(raw.get("manifest_digest", ""))
        data = dict(raw)
        data.pop("manifest_digest", None)
        data["adapter_digests"] = tuple(data.get("adapter_digests", ()))
        data["skill_digests"] = tuple(data.get("skill_digests", ()))
        m = cls(**data)
        m.validate()
        if expected and expected != m.digest:
            raise ValueError("governed runtime manifest digest mismatch")
        return m
