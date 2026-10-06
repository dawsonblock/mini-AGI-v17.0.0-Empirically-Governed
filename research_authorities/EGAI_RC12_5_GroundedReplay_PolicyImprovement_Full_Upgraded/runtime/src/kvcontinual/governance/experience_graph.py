from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, sqlite3
from egai.common.canonical import digest

@dataclass(frozen=True)
class GraphNode:
    node_id:str; kind:str; payload:dict; payload_digest:str
@dataclass(frozen=True)
class GraphEdge:
    src:str; relation:str; dst:str; evidence_digest:str=''

class ExperienceGraph:
    'Relational index. Evidence digests are references; this graph is not the truth store.'
    def __init__(self,path:str|Path):
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS nodes(node_id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload_json TEXT NOT NULL,payload_digest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS edges(src TEXT NOT NULL,relation TEXT NOT NULL,dst TEXT NOT NULL,evidence_digest TEXT NOT NULL DEFAULT '',PRIMARY KEY(src,relation,dst,evidence_digest),FOREIGN KEY(src) REFERENCES nodes(node_id),FOREIGN KEY(dst) REFERENCES nodes(node_id));
        CREATE INDEX IF NOT EXISTS edge_src ON edges(src); CREATE INDEX IF NOT EXISTS edge_dst ON edges(dst);
        '''); self.db.commit()
    def add_node(self,node_id,kind,payload):
        d=digest(payload)
        with self.db:self.db.execute('INSERT OR REPLACE INTO nodes VALUES (?,?,?,?)',(node_id,kind,json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False),d))
        return GraphNode(node_id,kind,payload,d)
    def link(self,src,relation,dst,evidence_digest=''):
        if not self.db.execute('SELECT 1 FROM nodes WHERE node_id=?',(src,)).fetchone() or not self.db.execute('SELECT 1 FROM nodes WHERE node_id=?',(dst,)).fetchone(): raise KeyError('both nodes must exist')
        with self.db:self.db.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?,?)',(src,relation,dst,evidence_digest))
        return GraphEdge(src,relation,dst,evidence_digest)
    def neighbors(self,node_id,relation=None):
        q='SELECT e.src,e.relation,e.dst,e.evidence_digest,n.kind,n.payload_json,n.payload_digest FROM edges e JOIN nodes n ON n.node_id=e.dst WHERE e.src=?'; a=[node_id]
        if relation is not None:q+=' AND e.relation=?';a.append(relation)
        return [(GraphEdge(r[0],r[1],r[2],r[3]),GraphNode(r[2],r[4],json.loads(r[5]),r[6])) for r in self.db.execute(q,a)]
