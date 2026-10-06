from pathlib import Path
from egai_v22.core.canonical import sha256_bytes, require_digest

class ArtifactStore:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def put(self,data:bytes):
        d=sha256_bytes(data); p=self.root/d[7:];
        if not p.exists(): p.write_bytes(data)
        return d
    def get(self,digest):
        require_digest(digest); p=self.root/digest[7:]
        if not p.is_file(): raise KeyError(digest)
        data=p.read_bytes()
        if sha256_bytes(data)!=digest: raise ValueError('artifact digest mismatch')
        return data
