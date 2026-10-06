from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json
from egai.common.canonical import digest

DEFAULT_EXCLUDED=(
    'references/','runtime/build/','runtime/dist/','.git/','.pytest_cache/','__pycache__/',
    'release/RC12_2_1_SOURCE_CLOSURE.json','release/RC12_3_APPLE_SOURCE_CLOSURE.json','release/RC12_3_1_TARGET_MAC_SOURCE_CLOSURE.json','release/RC12_4_FROZEN_TRANSFER_SOURCE_CLOSURE.json','release/wheels/','release/ARTIFACT_MANIFEST_RC12_2_1.json','release/ARTIFACT_MANIFEST_RC12_3_APPLE.json','release/ARTIFACT_MANIFEST_RC12_3_1_TARGET_MAC.json','release/ARTIFACT_MANIFEST_RC12_4_FROZEN_TRANSFER.json','release/source-manifest.sha256',
)

@dataclass(frozen=True)
class SourceFile:
    path:str
    sha256:str
    size:int

@dataclass(frozen=True)
class SourceClosure:
    version:str
    files:tuple[SourceFile,...]
    excluded_prefixes:tuple[str,...]
    closure_digest:str=''

def _excluded(rel:str,prefixes:tuple[str,...])->bool:
    if '/__pycache__/' in '/'+rel+'/': return True
    return any(rel==p.rstrip('/') or rel.startswith(p) for p in prefixes)

def build_source_closure(root:str|Path,version:str,excluded_prefixes=DEFAULT_EXCLUDED)->SourceClosure:
    root=Path(root); prefixes=tuple(excluded_prefixes); rows=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(root).as_posix()
        if _excluded(rel,prefixes): continue
        b=p.read_bytes(); rows.append(SourceFile(rel,'sha256:'+hashlib.sha256(b).hexdigest(),len(b)))
    unsigned={'version':version,'files':[asdict(x) for x in rows],'excluded_prefixes':list(prefixes)}
    return SourceClosure(version,tuple(rows),prefixes,digest(unsigned))

def write_source_closure(root:str|Path,out:str|Path,version:str)->SourceClosure:
    c=build_source_closure(root,version)
    Path(out).write_text(json.dumps(asdict(c),sort_keys=True,indent=2),encoding='utf-8')
    return c

def verify_source_closure(root:str|Path,manifest:str|Path)->bool:
    d=json.loads(Path(manifest).read_text())
    c=build_source_closure(root,d['version'],tuple(d['excluded_prefixes']))
    expected={x['path']:(x['sha256'],x['size']) for x in d['files']}
    actual={x.path:(x.sha256,x.size) for x in c.files}
    return expected==actual and d['closure_digest']==c.closure_digest
