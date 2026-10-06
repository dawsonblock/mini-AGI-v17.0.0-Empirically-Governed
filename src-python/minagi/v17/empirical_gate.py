from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class AuthorityIdentity:
    name: str
    key_id: str
    process_id: str
    def validate(self) -> None:
        if not self.name.strip() or not self.key_id.strip() or not self.process_id.strip():
            raise ValueError("authority identity fields must be non-empty")

@dataclass(frozen=True)
class EmpiricalQualificationBundle:
    preregistered: bool
    fresh_transfer_passed: bool
    retention_passed: bool
    falsification_passed: bool
    replay_policy_passed: bool
    live_canary_passed: bool
    security_regressions: int
    physical_closure_passed: bool
    proposer: AuthorityIdentity
    qualifier: AuthorityIdentity
    promoter: AuthorityIdentity

class V17PromotionGate:
    """Fail-closed final gate. It evaluates evidence; it does not perform learning."""
    @staticmethod
    def qualify(bundle: EmpiricalQualificationBundle) -> bool:
        for authority in (bundle.proposer, bundle.qualifier, bundle.promoter):
            authority.validate()
        identities = {(a.key_id, a.process_id) for a in (bundle.proposer, bundle.qualifier, bundle.promoter)}
        if len(identities) != 3:
            return False
        return all((bundle.preregistered, bundle.fresh_transfer_passed, bundle.retention_passed,
                    bundle.falsification_passed, bundle.replay_policy_passed,
                    bundle.live_canary_passed, bundle.physical_closure_passed)) and bundle.security_regressions == 0
