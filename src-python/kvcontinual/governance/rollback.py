from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from datetime import datetime, timezone
import json, os, tempfile
from egai.common.canonical import digest, validate_digest
from egai.common.crypto import SignedEnvelope

@dataclass(frozen=True)
class RuntimeState:
    runtime_digest:str
    base_model_digest:str
    component_digests:tuple[str,...]
    belief_snapshot_digest:str
    skill_snapshot_digest:str
    router_digest:str
    policy_digest:str
    artifact_root_digest:str
    def __post_init__(self):
        for x in (self.runtime_digest,self.base_model_digest,self.belief_snapshot_digest,self.skill_snapshot_digest,self.router_digest,self.policy_digest,self.artifact_root_digest,*self.component_digests): validate_digest(x)
    @property
    def closure_digest(self): return digest(self)

@dataclass(frozen=True)
class ActivationReceipt:
    action:str
    generation:int
    previous_runtime_digest:str
    previous_closure_digest:str
    runtime_digest:str
    closure_digest:str
    issued_at:str
    key_id:str=''
    signature_b64:str=''
    @property
    def unsigned(self): return asdict(replace(self,key_id='',signature_b64=''))

class AtomicRuntimePointer:
    def __init__(self,path:str|Path,*,signer=None,verifier=None,audit_path:str|Path|None=None,require_signature:bool=False):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.signer=signer; self.verifier=verifier; self.require_signature=require_signature
        self.audit_path=Path(audit_path) if audit_path else self.path.with_suffix(self.path.suffix+'.receipts.jsonl')

    def _fsync_dir(self):
        fd=os.open(str(self.path.parent),os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def _append_receipt(self,r:ActivationReceipt):
        self.audit_path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(self.audit_path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        try:
            os.write(fd,(json.dumps(asdict(r),sort_keys=True,separators=(',',':'))+'\n').encode()); os.fsync(fd)
        finally: os.close(fd)
        afd=os.open(str(self.audit_path.parent),os.O_RDONLY)
        try: os.fsync(afd)
        finally: os.close(afd)

    def _transition(self,state:RuntimeState,action:str)->ActivationReceipt:
        cur=self.current() or {}
        generation=int(cur.get('generation',0))+1
        prev_runtime=cur.get('runtime_digest',''); prev_closure=cur.get('closure_digest','')
        receipt=ActivationReceipt(action,generation,prev_runtime,prev_closure,state.runtime_digest,state.closure_digest,
                                  datetime.now(timezone.utc).isoformat())
        if self.signer is None:
            if self.require_signature: raise PermissionError('activation signer required')
        else:
            e=self.signer.sign(receipt.unsigned)
            receipt=replace(receipt,key_id=e.key_id,signature_b64=e.signature_b64)
        data={'runtime_digest':state.runtime_digest,'closure_digest':state.closure_digest,'generation':generation,
              'receipt_digest':digest(asdict(receipt))}
        fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix=self.path.name+'.')
        try:
            with os.fdopen(fd,'w') as f:
                f.write(json.dumps(data,sort_keys=True,separators=(',',':'))); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path); self._fsync_dir(); self._append_receipt(receipt)
        except Exception:
            try: os.unlink(tmp)
            except FileNotFoundError: pass
            raise
        return receipt

    def activate(self,state:RuntimeState): return self._transition(state,'activate')
    def rollback(self,state:RuntimeState): return self._transition(state,'rollback')
    def current(self): return None if not self.path.exists() else json.loads(self.path.read_text())

    def verify_receipt(self,r:ActivationReceipt)->bool:
        if not r.key_id or not r.signature_b64 or self.verifier is None: return False
        return self.verifier.verify(r.unsigned,SignedEnvelope(r.key_id,r.signature_b64))
