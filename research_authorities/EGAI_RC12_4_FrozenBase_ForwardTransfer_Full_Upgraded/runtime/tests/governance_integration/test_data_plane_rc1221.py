import json, sqlite3
from kvcontinual.governance.data_plane import GovernanceDataPlane,SCHEMA_VERSION

def test_chain_recomputes_payload_digest_and_detects_tamper(tmp_path):
    p=tmp_path/'g.db'; s=GovernanceDataPlane(p); s.put('belief','x',{'v':1}); s.put('belief','x',{'v':2}); assert s.verify_chain('belief','x'); s.close()
    db=sqlite3.connect(p); db.execute('UPDATE versions SET value_json=? WHERE namespace=? AND key=? AND version=?',(json.dumps({'v':999}),'belief','x',2)); db.commit(); db.close()
    s=GovernanceDataPlane(p); assert not s.verify_chain('belief','x'); s.close()

def test_schema_v1_migrates_and_tx_ids_are_present(tmp_path):
    p=tmp_path/'v1.db'; db=sqlite3.connect(p)
    db.executescript('CREATE TABLE schema_meta(version INTEGER NOT NULL); INSERT INTO schema_meta VALUES (1); CREATE TABLE versions(namespace TEXT NOT NULL,key TEXT NOT NULL,version INTEGER NOT NULL,value_json TEXT NOT NULL,value_digest TEXT NOT NULL,previous_digest TEXT NOT NULL,created_at_ns INTEGER NOT NULL,tombstone INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(namespace,key,version));')
    db.commit(); db.close(); s=GovernanceDataPlane(p); assert s.db.execute('SELECT version FROM schema_meta').fetchone()[0]==SCHEMA_VERSION; r=s.put('x','y',{'a':1}); assert r.tx_id; s.close()
