import json, hashlib
from dataclasses import asdict, is_dataclass
from enum import Enum

_SHA256_PREFIX='sha256:'

def _norm(v):
    if is_dataclass(v): return _norm(asdict(v))
    if isinstance(v, Enum): return v.value
    if isinstance(v, dict): return {str(k): _norm(v[k]) for k in sorted(v)}
    if isinstance(v, (list,tuple)): return [_norm(x) for x in v]
    return v

def canonical_json(obj):
    return json.dumps(_norm(obj), sort_keys=True, separators=(',',':'), ensure_ascii=False)

def sha256_bytes(data: bytes):
    return _SHA256_PREFIX + hashlib.sha256(data).hexdigest()

def sha256_obj(obj):
    return sha256_bytes(canonical_json(obj).encode())

def require_digest(d):
    if not isinstance(d,str) or len(d)!=71 or not d.startswith(_SHA256_PREFIX):
        raise ValueError('invalid sha256 digest')
    int(d[7:],16)
    return d
