from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json, sqlite3, time, uuid
from egai.common.canonical import digest

SCHEMA_VERSION = 2

@dataclass(frozen=True)
class VersionedRecord:
    namespace: str
    key: str
    version: int
    value: dict[str, Any]
    value_digest: str
    previous_digest: str
    created_at_ns: int
    tombstone: bool = False
    tx_id: str = ''

class GovernanceDataPlane:
    'Transactional derived-state store. Historical evidence remains in the evidence ledger.'
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30.0)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self._migrate()

    def _migrate(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS versions(
          namespace TEXT NOT NULL,
          key TEXT NOT NULL,
          version INTEGER NOT NULL,
          value_json TEXT NOT NULL,
          value_digest TEXT NOT NULL,
          previous_digest TEXT NOT NULL,
          created_at_ns INTEGER NOT NULL,
          tombstone INTEGER NOT NULL DEFAULT 0,
          tx_id TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(namespace,key,version)
        );
        CREATE INDEX IF NOT EXISTS idx_versions_digest ON versions(value_digest);
        CREATE INDEX IF NOT EXISTS idx_versions_latest ON versions(namespace,key,version DESC);
        ''')
        row = self.db.execute('SELECT version FROM schema_meta LIMIT 1').fetchone()
        if row is None:
            self.db.execute('INSERT INTO schema_meta(version) VALUES (?)',(SCHEMA_VERSION,))
        elif row[0] == 1:
            cols={r[1] for r in self.db.execute('PRAGMA table_info(versions)')}
            if 'tx_id' not in cols:
                self.db.execute("ALTER TABLE versions ADD COLUMN tx_id TEXT NOT NULL DEFAULT ''")
            rows=self.db.execute("SELECT namespace,key,version FROM versions WHERE tx_id='' OR tx_id IS NULL").fetchall()
            for ns,key,ver in rows:
                self.db.execute('UPDATE versions SET tx_id=? WHERE namespace=? AND key=? AND version=?',
                                (f'legacy:{ns}:{key}:{ver}',ns,key,ver))
            self.db.execute('UPDATE schema_meta SET version=?',(SCHEMA_VERSION,))
        elif row[0] != SCHEMA_VERSION:
            raise RuntimeError(f'unsupported governance schema {row[0]}')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_versions_tx ON versions(tx_id)')
        self.db.commit()

    def _begin(self):
        self.db.execute('BEGIN IMMEDIATE')

    def put(self, namespace: str, key: str, value: dict[str,Any], *, expected_version: int | None = None,
            tx_id: str | None = None) -> VersionedRecord:
        if not namespace or not key: raise ValueError('namespace/key required')
        payload = json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        value_digest = digest(value)
        now = time.time_ns(); tx_id = tx_id or uuid.uuid4().hex
        try:
            self._begin()
            row = self.db.execute('SELECT version,value_digest FROM versions WHERE namespace=? AND key=? ORDER BY version DESC LIMIT 1',(namespace,key)).fetchone()
            current = row[0] if row else 0; prev = row[1] if row else ''
            if expected_version is not None and current != expected_version:
                raise RuntimeError(f'version conflict: expected {expected_version}, found {current}')
            version=current+1
            self.db.execute('INSERT INTO versions(namespace,key,version,value_json,value_digest,previous_digest,created_at_ns,tombstone,tx_id) VALUES (?,?,?,?,?,?,?,?,?)',
                            (namespace,key,version,payload,value_digest,prev,now,0,tx_id))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return VersionedRecord(namespace,key,version,value,value_digest,prev,now,False,tx_id)

    def tombstone(self, namespace: str, key: str, *, expected_version: int | None = None,
                  tx_id: str | None = None) -> VersionedRecord:
        tx_id=tx_id or uuid.uuid4().hex; now=time.time_ns()
        try:
            self._begin()
            row=self.db.execute('SELECT version,value_digest FROM versions WHERE namespace=? AND key=? ORDER BY version DESC LIMIT 1',(namespace,key)).fetchone()
            current=row[0] if row else 0; prev=row[1] if row else ''
            if expected_version is not None and current != expected_version: raise RuntimeError('version conflict')
            d=digest({'tombstone':True,'previous':prev})
            self.db.execute('INSERT INTO versions(namespace,key,version,value_json,value_digest,previous_digest,created_at_ns,tombstone,tx_id) VALUES (?,?,?,?,?,?,?,?,?)',
                            (namespace,key,current+1,'{}',d,prev,now,1,tx_id))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return VersionedRecord(namespace,key,current+1,{},d,prev,now,True,tx_id)

    @staticmethod
    def _from_row(namespace,key,r):
        return VersionedRecord(namespace,key,r[0],json.loads(r[1]),r[2],r[3],r[4],bool(r[5]),r[6])

    def latest(self, namespace: str, key: str) -> VersionedRecord | None:
        r=self.db.execute('SELECT version,value_json,value_digest,previous_digest,created_at_ns,tombstone,tx_id FROM versions WHERE namespace=? AND key=? ORDER BY version DESC LIMIT 1',(namespace,key)).fetchone()
        return None if not r else self._from_row(namespace,key,r)

    def get_version(self, namespace: str, key: str, version: int) -> VersionedRecord:
        r=self.db.execute('SELECT version,value_json,value_digest,previous_digest,created_at_ns,tombstone,tx_id FROM versions WHERE namespace=? AND key=? AND version=?',(namespace,key,version)).fetchone()
        if not r: raise KeyError((namespace,key,version))
        return self._from_row(namespace,key,r)

    def history(self, namespace: str, key: str) -> list[VersionedRecord]:
        rows=self.db.execute('SELECT version,value_json,value_digest,previous_digest,created_at_ns,tombstone,tx_id FROM versions WHERE namespace=? AND key=? ORDER BY version',(namespace,key)).fetchall()
        return [self._from_row(namespace,key,r) for r in rows]

    def verify_chain(self, namespace: str, key: str) -> bool:
        prev=''; expected_version=1
        for r in self.history(namespace,key):
            if r.version != expected_version or r.previous_digest != prev or not r.tx_id: return False
            expected = digest({'tombstone':True,'previous':prev}) if r.tombstone else digest(r.value)
            if r.value_digest != expected: return False
            prev=r.value_digest; expected_version+=1
        return True

    def verify_all(self) -> bool:
        keys=self.db.execute('SELECT DISTINCT namespace,key FROM versions').fetchall()
        return all(self.verify_chain(ns,key) for ns,key in keys)

    def close(self): self.db.close()
