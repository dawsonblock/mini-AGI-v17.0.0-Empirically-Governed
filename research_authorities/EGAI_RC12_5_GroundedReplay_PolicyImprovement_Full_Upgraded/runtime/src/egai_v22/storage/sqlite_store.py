import sqlite3, json
from egai_v22.core.canonical import canonical_json, sha256_obj

SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, prev_chain TEXT NOT NULL, chain_digest TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, object_digest TEXT NOT NULL, payload TEXT NOT NULL, prev_chain TEXT NOT NULL, chain_digest TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS derived_state(key TEXT PRIMARY KEY, value TEXT NOT NULL, promotion_digest TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS derived_history(seq INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, old_value TEXT, new_value TEXT, promotion_digest TEXT NOT NULL, action TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS improvements(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
"""

class SQLiteAuthorityStore:
    def __init__(self,path=':memory:'):
        self.path=str(path); self.db=sqlite3.connect(self.path); self.db.executescript(SCHEMA); self.db.commit()
        self._evidence_authority=None
    def bind_evidence_capability_authority(self,authority): self._evidence_authority=authority
    def _head(self,table):
        order='seq' if table=='audit' else 'rowid'
        row=self.db.execute(f'SELECT chain_digest FROM {table} ORDER BY {order} DESC LIMIT 1').fetchone()
        return row[0] if row else 'GENESIS'
    def append_evidence(self, record, _capability=None):
        if self._evidence_authority is None or not self._evidence_authority.validate(_capability,'EVIDENCE_ADMISSION_INTERNAL'):
            raise PermissionError('evidence admission capability required')
        prev=self._head('evidence'); digest=record.digest(); chain=sha256_obj({'prev':prev,'record':digest})
        self.db.execute('INSERT INTO evidence VALUES(?,?,?,?,?)',(record.evidence_id,digest,canonical_json(record),prev,chain)); self.db.commit(); return digest
    def append_audit(self, kind, obj):
        prev=self._head('audit'); od=obj.digest() if hasattr(obj,'digest') else sha256_obj(obj); chain=sha256_obj({'prev':prev,'kind':kind,'object':od})
        self.db.execute('INSERT INTO audit(kind,object_digest,payload,prev_chain,chain_digest) VALUES(?,?,?,?,?)',(kind,od,canonical_json(obj),prev,chain)); self.db.commit(); return chain
    def commit_derived(self,key,value,promotion_digest,_capability=None):
        if _capability!='PROMOTION_AUTHORITY_INTERNAL': raise PermissionError('promotion capability required')
        old=self.db.execute('SELECT value,version FROM derived_state WHERE key=?',(key,)).fetchone()
        old_value=old[0] if old else None; version=(old[1]+1) if old else 1
        nv=canonical_json(value)
        self.db.execute('INSERT OR REPLACE INTO derived_state(key,value,promotion_digest,version) VALUES(?,?,?,?)',(key,nv,promotion_digest,version))
        self.db.execute('INSERT INTO derived_history(key,old_value,new_value,promotion_digest,action) VALUES(?,?,?,?,?)',(key,old_value,nv,promotion_digest,'commit'))
        self.db.commit(); return version
    def rollback_derived(self,key,rollback_value,promotion_digest,_capability=None):
        if _capability!='PROMOTION_AUTHORITY_INTERNAL': raise PermissionError('promotion capability required')
        old=self.db.execute('SELECT value,version FROM derived_state WHERE key=?',(key,)).fetchone()
        if not old: raise KeyError(key)
        nv=canonical_json(rollback_value); version=old[1]+1
        self.db.execute('UPDATE derived_state SET value=?,promotion_digest=?,version=? WHERE key=?',(nv,promotion_digest,version,key))
        self.db.execute('INSERT INTO derived_history(key,old_value,new_value,promotion_digest,action) VALUES(?,?,?,?,?)',(key,old[0],nv,promotion_digest,'rollback'))
        self.db.commit(); return version
    def get_derived(self,key):
        r=self.db.execute('SELECT value FROM derived_state WHERE key=?',(key,)).fetchone(); return None if not r else json.loads(r[0])
    def get_version(self,key):
        r=self.db.execute('SELECT version FROM derived_state WHERE key=?',(key,)).fetchone(); return None if not r else r[0]
    def history(self,key):
        return self.db.execute('SELECT seq,old_value,new_value,promotion_digest,action FROM derived_history WHERE key=? ORDER BY seq',(key,)).fetchall()
    def put_improvement(self, rec):
        self.db.execute('INSERT INTO improvements VALUES(?,?)',(rec.improvement_id,canonical_json(rec))); self.db.commit()
    def get_improvements(self):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM improvements ORDER BY rowid')]
    def verify_chains(self):
        prev='GENESIS'
        for digest,p,chain in self.db.execute('SELECT digest,prev_chain,chain_digest FROM evidence ORDER BY rowid'):
            if p!=prev or sha256_obj({'prev':prev,'record':digest})!=chain: return False
            prev=chain
        prev='GENESIS'
        for kind,od,p,chain in self.db.execute('SELECT kind,object_digest,prev_chain,chain_digest FROM audit ORDER BY seq'):
            if p!=prev or sha256_obj({'prev':prev,'kind':kind,'object':od})!=chain: return False
            prev=chain
        return True
