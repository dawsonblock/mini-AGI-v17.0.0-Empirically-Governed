from dataclasses import dataclass

ROLES=("benchmark","builder","runner","evaluator","qualifier","promotion","rollback")

@dataclass(frozen=True)
class AuthorityTrust:
    roles: dict[str, tuple[str,...]]
    revoked_keys: frozenset[str] = frozenset()

    def __post_init__(self):
        unknown=set(self.roles)-set(ROLES)
        if unknown: raise ValueError(f"unknown trust roles: {sorted(unknown)}")
        object.__setattr__(self, "roles", {str(k): tuple(str(x) for x in v) for k,v in self.roles.items()})
        object.__setattr__(self, "revoked_keys", frozenset(str(x) for x in self.revoked_keys))

    def require(self, role:str, key_id:str):
        if key_id in self.revoked_keys:
            raise PermissionError(f"revoked {role} key: {key_id!r}")
        allowed=set(self.roles.get(role,()))
        if not key_id or key_id not in allowed:
            raise PermissionError(f"untrusted {role} key: {key_id!r}")

    def revoke(self, *key_ids: str):
        return AuthorityTrust(self.roles, revoked_keys=self.revoked_keys.union(str(x) for x in key_ids))

    @classmethod
    def from_signers(cls, **role_to_signer):
        return cls({r:(s.key_id,) for r,s in role_to_signer.items()})
