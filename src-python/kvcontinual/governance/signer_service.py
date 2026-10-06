from __future__ import annotations
import json, os, socket, socketserver, threading, secrets, time, sqlite3, hashlib
from pathlib import Path
from egai.common.canonical import validate_digest

_DEFAULT_ALLOWED = frozenset({'qualification','promotion','fresh-task'})

class SignerReplayStore:
    'Durable anti-replay registry. A request ID remains consumed across process restarts.'
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY,purpose TEXT NOT NULL,digest TEXT NOT NULL,ts_ns INTEGER NOT NULL,accepted_at_ns INTEGER NOT NULL)')
        self.db.commit()
        self.lock = threading.Lock()

    def consume(self, request_id: str, purpose: str, digest: str, ts_ns: int) -> bool:
        with self.lock:
            try:
                with self.db:
                    self.db.execute('INSERT INTO requests VALUES (?,?,?,?,?)',
                                    (request_id,purpose,digest,int(ts_ns),time.time_ns()))
                return True
            except sqlite3.IntegrityError:
                return False

    def close(self):
        self.db.close()

class _H(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            r = json.loads(self.rfile.readline())
        except Exception:
            self.wfile.write(b'{"error":"malformed request"}\n'); return
        p = r.get('purpose','')
        d = r.get('digest','')
        rid = r.get('request_id','')
        ts = r.get('ts_ns')
        now = time.time_ns()
        if p not in self.server.allowed_purposes:
            self.wfile.write(b'{"error":"purpose denied"}\n'); return
        try:
            validate_digest(d)
        except Exception:
            self.wfile.write(b'{"error":"invalid digest"}\n'); return
        if not isinstance(rid,str) or len(rid) < 16:
            self.wfile.write(b'{"error":"request_id required"}\n'); return
        if not isinstance(ts,int):
            self.wfile.write(b'{"error":"ts_ns required"}\n'); return
        if ts < now-self.server.max_age_ns or ts > now+self.server.max_future_skew_ns:
            self.wfile.write(b'{"error":"stale or future request"}\n'); return
        if not self.server.replay.consume(rid,p,d,ts):
            self.wfile.write(b'{"error":"replayed request"}\n'); return
        signed = {'purpose':p,'digest':d,'request_id':rid,'ts_ns':ts,'authority_id':self.server.authority_id}
        e = self.server.signer.sign(signed)
        out = {'key_id':e.key_id,'signature_b64':e.signature_b64,'request_id':rid,
               'ts_ns':ts,'authority_id':self.server.authority_id}
        self.wfile.write((json.dumps(out,sort_keys=True,separators=(',',':'))+'\n').encode())

class _S(socketserver.UnixStreamServer):
    def __init__(self,path,signer,replay_store,allowed_purposes,authority_id,max_age_ns,max_future_skew_ns):
        if os.path.exists(path): os.unlink(path)
        self.signer=signer
        self.replay=replay_store
        self.allowed_purposes=frozenset(allowed_purposes)
        self.authority_id=authority_id
        self.max_age_ns=int(max_age_ns)
        self.max_future_skew_ns=int(max_future_skew_ns)
        super().__init__(path,_H)
        os.chmod(path,0o600)

class SignerService:
    'Unix-socket signer boundary with persistent replay defense and purpose scoping.'
    def __init__(self,path,signer,*,replay_store_path=None,allowed_purposes=None,
                 authority_id=None,max_age_s=300.0,max_future_skew_s=5.0):
        self.path=str(path)
        replay_path = Path(replay_store_path or (self.path+'.replay.sqlite3'))
        self.replay = SignerReplayStore(replay_path)
        self.server=_S(self.path,signer,self.replay,allowed_purposes or _DEFAULT_ALLOWED,
                       authority_id or signer.key_id,int(max_age_s*1e9),int(max_future_skew_s*1e9))
        self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start(); return self

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.replay.close()
        try: os.unlink(self.path)
        except FileNotFoundError: pass

def request_signature(path,purpose,d,request_id=None,ts_ns=None):
    validate_digest(d)
    rid=request_id or secrets.token_hex(16)
    if len(rid)<16:
        rid='compat-'+hashlib.sha256(rid.encode()).hexdigest()[:32]
    r={'purpose':purpose,'digest':d,
       'request_id':rid,
       'ts_ns':int(ts_ns if ts_ns is not None else time.time_ns())}
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.connect(path)
        s.sendall((json.dumps(r,sort_keys=True,separators=(',',':'))+'\n').encode())
        return json.loads(s.makefile().readline())
