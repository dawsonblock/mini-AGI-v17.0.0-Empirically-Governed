from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from pathlib import Path
import hashlib, json, os, sqlite3, tempfile, zipfile
import numpy as np

from kvcontinual.execution.attention.relocation import FullAttentionRelocationMetadata
from kvcontinual.execution.cache.block import ArtifactQualification, BoundaryAnchors, ExecutionArtifact, RecurrentTailArtifact
from kvcontinual.execution.durability.cas import ContentAddressedStore
from kvcontinual.execution.recurrent.affine import AffineSummary
from kvcontinual.execution.recurrent.conv_boundary import ConvBoundaryState
from kvcontinual.execution.types import CacheTier, ExecutionIdentity, ModelIdentity, TransitionOrientation

_SCHEMA=1


def _json_safe(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):_json_safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_json_safe(x) for x in v]
    raise TypeError(f"non-JSON metadata type: {type(v).__name__}")


def encode_artifact(a: ExecutionArtifact) -> bytes:
    a.validate(); arrays={}
    def add(name, arr):
        arr=np.asarray(arr)
        bio=BytesIO(); np.save(bio,arr,allow_pickle=False); data=bio.getvalue()
        arrays[name]=data
        return {'entry':name,'sha256':hashlib.sha256(data).hexdigest(),'dtype':str(arr.dtype),'shape':list(arr.shape)}
    rec=[]
    for (layer,head), r in sorted(a.recurrent.items()):
        item={'layer':layer,'head':head,'seam_width':r.seam_width,'orientation':r.tail_summary.orientation.value,
              'T':add(f'arrays/recurrent-{layer}-{head}-T.npy',r.tail_summary.T),
              'Z':add(f'arrays/recurrent-{layer}-{head}-Z.npy',r.tail_summary.Z),
              'stats':_json_safe(r.stats)}
        if r.trailing_conv_payload is not None: item['trailing_conv_payload']=add(f'arrays/recurrent-{layer}-{head}-conv.npy',r.trailing_conv_payload)
        rec.append(item)
    conv=[]
    for layer,c in sorted(a.conv_boundaries.items()): conv.append({'layer':layer,'kernel_size':c.kernel_size,'history':add(f'arrays/conv-{layer}.npy',c.history)})
    bound={'leading_tokens':list(a.boundary.leading_tokens),'original_hidden':{},'original_attention_output':{},'original_route_ids':{}}
    for field in ('original_hidden','original_attention_output','original_route_ids'):
        for k,v in sorted(getattr(a.boundary,field).items()): bound[field][str(k)]=add(f'arrays/boundary-{field}-{k}.npy',v)
    ident={'model':asdict(a.identity.model),**{k:v for k,v in asdict(a.identity).items() if k!='model'}}
    man={'schema':_SCHEMA,'artifact_id':a.artifact_id,'source_segment_id':a.source_segment_id,'source_content_digest':a.source_content_digest,
         'identity':ident,'identity_digest':a.identity.digest,'fixed_seam_width':a.fixed_seam_width,'recurrent':rec,'conv_boundaries':conv,
         'attention_kv_ref':a.attention_kv_ref,'position_metadata':_json_safe(a.position_metadata),'boundary':bound,
         'attention_relocation':[asdict(v) for _,v in sorted(a.attention_relocation.items())],
         'capture_manifest_digest':a.capture_manifest_digest,'qualification':None if a.qualification is None else asdict(a.qualification),
         'tier':a.tier.value,'byte_size':a.byte_size,'created_at':a.created_at}
    mbytes=json.dumps(man,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    out=BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
        for name,data in [('manifest.json',mbytes),*sorted(arrays.items())]:
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_STORED; info.external_attr=0o100644<<16
            z.writestr(info,data)
    return out.getvalue()


def decode_artifact(data: bytes) -> ExecutionArtifact:
    with zipfile.ZipFile(BytesIO(data),'r') as z:
        names=set(z.namelist())
        if 'manifest.json' not in names: raise ValueError('artifact manifest missing')
        m=json.loads(z.read('manifest.json'))
        if m.get('schema')!=_SCHEMA: raise ValueError('unsupported artifact schema')
        def arr(spec):
            name=spec['entry']
            if name not in names: raise ValueError(f'missing array {name}')
            raw=z.read(name)
            if hashlib.sha256(raw).hexdigest()!=spec['sha256']: raise ValueError(f'array digest mismatch: {name}')
            a=np.load(BytesIO(raw),allow_pickle=False)
            if list(a.shape)!=spec['shape'] or str(a.dtype)!=spec['dtype']: raise ValueError(f'array metadata mismatch: {name}')
            return a
        md=m['identity']['model']; model=ModelIdentity(**md)
        idkw={k:v for k,v in m['identity'].items() if k!='model'}; ident=ExecutionIdentity(model=model,**idkw)
        if ident.digest!=m['identity_digest']: raise ValueError('execution identity digest mismatch')
        recurrent={}
        for r in m['recurrent']:
            key=(int(r['layer']),int(r['head']))
            recurrent[key]=RecurrentTailArtifact(layer=key[0],head=key[1],seam_width=int(r['seam_width']),
                tail_summary=AffineSummary(arr(r['T']),arr(r['Z']),TransitionOrientation(r['orientation'])),
                trailing_conv_payload=arr(r['trailing_conv_payload']) if 'trailing_conv_payload' in r else None,stats=dict(r.get('stats',{})))
        conv={int(c['layer']):ConvBoundaryState(arr(c['history']),int(c['kernel_size'])) for c in m['conv_boundaries']}
        b=m['boundary']; boundary=BoundaryAnchors(leading_tokens=list(b['leading_tokens']))
        for field in ('original_hidden','original_attention_output','original_route_ids'):
            setattr(boundary,field,{int(k):arr(v) for k,v in b[field].items()})
        reloc={int(x['layer']):FullAttentionRelocationMetadata(**x) for x in m['attention_relocation']}
        q=ArtifactQualification(**m['qualification']) if m['qualification'] is not None else None
        a=ExecutionArtifact(source_segment_id=m['source_segment_id'],identity=ident,fixed_seam_width=int(m['fixed_seam_width']),recurrent=recurrent,
            attention_kv_ref=m.get('attention_kv_ref'),position_metadata=m.get('position_metadata',{}),boundary=boundary,conv_boundaries=conv,
            attention_relocation=reloc,capture_manifest_digest=m.get('capture_manifest_digest',''),qualification=q,tier=CacheTier(m['tier']),
            byte_size=int(m.get('byte_size',0)),source_content_digest=m.get('source_content_digest',''),artifact_id=m['artifact_id'],created_at=m['created_at'])
        a.validate(); return a


class PersistentExecutionArtifactStore:
    """Crash-safe persistent execution-artifact store backed by SHA-256 CAS + SQLite index.

    SQLite stores only lookup metadata. Artifact bytes are immutable CAS objects and are
    verified before deserialization. Corrupt objects fail closed and are quarantined.
    """
    def __init__(self, root: str|Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.cas=ContentAddressedStore(self.root/'objects')
        self.db=sqlite3.connect(self.root/'index.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS artifacts (source_segment_id TEXT NOT NULL, identity_digest TEXT NOT NULL, source_content_digest TEXT NOT NULL, object_digest TEXT NOT NULL, tier TEXT NOT NULL, byte_size INTEGER NOT NULL, PRIMARY KEY(source_segment_id,identity_digest))')
        self.db.commit()
    def close(self): self.db.close()
    def put(self,a:ExecutionArtifact)->None:
        payload=encode_artifact(a); obj=self.cas.put(payload)
        with self.db:
            self.db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?) ON CONFLICT(source_segment_id,identity_digest) DO UPDATE SET source_content_digest=excluded.source_content_digest,object_digest=excluded.object_digest,tier=excluded.tier,byte_size=excluded.byte_size',
                (a.source_segment_id,a.identity.digest,a.source_content_digest,obj.digest,a.tier.value,a.byte_size))
    def get(self,source_segment_id:str,identity:ExecutionIdentity,source_content_digest:str|None=None):
        row=self.db.execute('SELECT source_content_digest,object_digest FROM artifacts WHERE source_segment_id=? AND identity_digest=?',(source_segment_id,identity.digest)).fetchone()
        if row is None: return None
        if source_content_digest is not None and row[0] and row[0]!=source_content_digest: return None
        try: payload=self.cas.get(row[1]); a=decode_artifact(payload)
        except Exception:
            self.cas.verify_or_quarantine(row[1])
            with self.db: self.db.execute('DELETE FROM artifacts WHERE source_segment_id=? AND identity_digest=?',(source_segment_id,identity.digest))
            return None
        if a.identity.digest!=identity.digest or a.source_segment_id!=source_segment_id: return None
        return a
    def resolve(self,source_segment_ids:list[str],identity:ExecutionIdentity,source_content_digests:dict[str,str]|None=None):
        hits=[]; misses=[]
        for sid in source_segment_ids:
            a=self.get(sid,identity,source_content_digests.get(sid) if source_content_digests else None)
            (hits if a is not None else misses).append(a if a is not None else sid)
        return hits,misses
    def move_tier(self,source_segment_id:str,identity:ExecutionIdentity,tier:CacheTier)->None:
        a=self.get(source_segment_id,identity)
        if a is None: raise KeyError(source_segment_id)
        a.tier=tier; self.put(a)
    def evict_namespace(self,identity:ExecutionIdentity)->int:
        with self.db:
            cur=self.db.execute('DELETE FROM artifacts WHERE identity_digest=?',(identity.digest,))
        return int(cur.rowcount)
    def bytes_by_tier(self):
        return {row[0]:int(row[1]) for row in self.db.execute('SELECT tier,COALESCE(SUM(byte_size),0) FROM artifacts GROUP BY tier')}
    def verify_all(self)->dict[str,int]:
        ok=bad=0
        rows=list(self.db.execute('SELECT source_segment_id,identity_digest,object_digest FROM artifacts'))
        for sid,ident,d in rows:
            if self.cas.verify(d): ok+=1
            else:
                bad+=1; self.cas.verify_or_quarantine(d)
                with self.db: self.db.execute('DELETE FROM artifacts WHERE source_segment_id=? AND identity_digest=?',(sid,ident))
        return {'ok':ok,'bad':bad}
