from dataclasses import dataclass,asdict,replace
from datetime import datetime,timezone
from pathlib import Path
import secrets,sqlite3
from egai.common.canonical import digest
from egai.common.crypto import SignedEnvelope
@dataclass(frozen=True)
class FreshTaskCommitment:
    suite_id:str; generation:int; sealed_suite_digest:str; created_at:str; registrar_id:str; key_id:str=''; signature_b64:str=''
    @property
    def digest(self):return digest(asdict(replace(self,key_id='',signature_b64='')))
@dataclass(frozen=True)
class FreshTaskLease:
    lease_id:str; suite_id:str; generation:int; runner_id:str; candidate_digest:str; commitment_digest:str; nonce:str; issued_at:str; key_id:str=''; signature_b64:str=''
class FreshTaskStore:
    def __init__(self,path):
        self.db=sqlite3.connect(Path(path));self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript("CREATE TABLE IF NOT EXISTS generations(suite_id TEXT PRIMARY KEY,generation INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS commitments(suite_id TEXT NOT NULL,generation INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(suite_id,generation));CREATE TABLE IF NOT EXISTS consumed(suite_id TEXT NOT NULL,generation INTEGER NOT NULL,candidate_digest TEXT NOT NULL,PRIMARY KEY(suite_id,generation,candidate_digest));");self.db.commit()
    def next_generation(self,suite_id):
        with self.db:
            r=self.db.execute('SELECT generation FROM generations WHERE suite_id=?',(suite_id,)).fetchone();g=(r[0] if r else 0)+1;self.db.execute('INSERT INTO generations VALUES (?,?) ON CONFLICT(suite_id) DO UPDATE SET generation=excluded.generation',(suite_id,g))
        return g
    def save_commitment(self,c):
        import json
        with self.db:self.db.execute('INSERT OR REPLACE INTO commitments VALUES (?,?,?)',(c.suite_id,c.generation,json.dumps(asdict(c),sort_keys=True)))
    def load_commitment(self,suite_id,generation):
        import json
        r=self.db.execute('SELECT payload FROM commitments WHERE suite_id=? AND generation=?',(suite_id,generation)).fetchone();return FreshTaskCommitment(**json.loads(r[0])) if r else None
    def consume_once(self,suite_id,generation,candidate_digest):
        try:
            with self.db:self.db.execute('INSERT INTO consumed VALUES (?,?,?)',(suite_id,generation,candidate_digest))
            return True
        except sqlite3.IntegrityError:return False
class FreshTaskAuthority:
    def __init__(self,authority_id,signer,verifier,trust=None,store:FreshTaskStore|None=None):self.authority_id=authority_id;self.signer=signer;self.verifier=verifier;self.trust=trust;self.store=store;self._g={};self._c={};self._used=set()
    def commit_suite(self,suite_id,sealed_suite_digest):
        g=self.store.next_generation(suite_id) if self.store else self._g.get(suite_id,0)+1;self._g[suite_id]=g;u=FreshTaskCommitment(suite_id,g,sealed_suite_digest,datetime.now(timezone.utc).isoformat(),self.authority_id);e=self.signer.sign(asdict(u));c=replace(u,key_id=e.key_id,signature_b64=e.signature_b64);self._c[(suite_id,g)]=c
        if self.store:self.store.save_commitment(c)
        return c
    def _commitment(self,suite_id,generation):return self._c.get((suite_id,generation)) or (self.store.load_commitment(suite_id,generation) if self.store else None)
    def verify_commitment(self,c):
        if self.trust is not None:self.trust.require('benchmark',c.key_id)
        return self.verifier.verify(asdict(replace(c,key_id='',signature_b64='')),SignedEnvelope(c.key_id,c.signature_b64))
    def issue_lease(self,suite_id,generation,runner_id,candidate_digest):
        c=self._commitment(suite_id,generation)
        if c is None:raise KeyError('unknown commitment')
        if not self.verify_commitment(c):raise PermissionError('invalid commitment')
        k=(suite_id,generation,candidate_digest);fresh=self.store.consume_once(*k) if self.store else k not in self._used
        if not fresh:raise RuntimeError('fresh task generation already consumed by candidate')
        self._used.add(k);u=FreshTaskLease(secrets.token_hex(16),suite_id,generation,runner_id,candidate_digest,c.digest,secrets.token_hex(16),datetime.now(timezone.utc).isoformat());e=self.signer.sign(asdict(u));return replace(u,key_id=e.key_id,signature_b64=e.signature_b64)
    def verify_lease(self,l):
        c=self._commitment(l.suite_id,l.generation);return bool(c and l.commitment_digest==c.digest and self.verifier.verify(asdict(replace(l,key_id='',signature_b64='')),SignedEnvelope(l.key_id,l.signature_b64)))
