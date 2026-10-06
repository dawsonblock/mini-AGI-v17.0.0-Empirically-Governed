from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import json,time,os
from egai.common.canonical import digest
@dataclass(frozen=True)
class AuditEvent:
    seq:int; ts_ns:int; plane:str; event_type:str; payload:dict; prev_digest:str; event_digest:str
class AuditJournal:
    def __init__(self,path:str|Path):self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.path.touch(exist_ok=True)
    def _last(self):
        last=None
        with self.path.open() as f:
            for line in f:
                if line.strip():last=json.loads(line)
        return (-1,'') if last is None else (last['seq'],last['event_digest'])
    def emit(self,plane,event_type,payload):
        seq,prev=self._last();core={'seq':seq+1,'ts_ns':time.time_ns(),'plane':plane,'event_type':event_type,'payload':payload,'prev_digest':prev};d=digest(core);e=AuditEvent(event_digest=d,**core)
        fd=os.open(self.path,os.O_WRONLY|os.O_APPEND)
        try:os.write(fd,(json.dumps(asdict(e),sort_keys=True,separators=(',',':'))+'\n').encode());os.fsync(fd)
        finally:os.close(fd)
        return e
    def verify(self):
        prev='';seq=0
        with self.path.open() as f:
            for line in f:
                if not line.strip():continue
                x=json.loads(line);d=x.pop('event_digest')
                if x['seq']!=seq or x['prev_digest']!=prev or digest(x)!=d:return False
                prev=d;seq+=1
        return True
