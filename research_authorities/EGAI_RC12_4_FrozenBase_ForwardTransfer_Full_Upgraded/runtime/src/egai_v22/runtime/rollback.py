from dataclasses import dataclass
from egai_v22.core.canonical import sha256_obj

@dataclass(frozen=True)
class RollbackRecord:
    rollback_id:str
    key:str
    from_promotion_digest:str
    to_value_digest:str
    authorized_by:str
    reason:str
    def digest(self): return sha256_obj(self)

class RollbackAuthority:
    def __init__(self,version='rollback-v1'): self.version=version
    def rollback(self,store,key,to_value,from_promotion_digest,reason):
        rec=RollbackRecord('rb:'+sha256_obj({'key':key,'from':from_promotion_digest,'to':to_value})[7:23],key,from_promotion_digest,sha256_obj(to_value),self.version,reason)
        store.rollback_derived(key,to_value,rec.digest(),_capability='PROMOTION_AUTHORITY_INTERNAL')
        store.append_audit('rollback',rec)
        return rec
