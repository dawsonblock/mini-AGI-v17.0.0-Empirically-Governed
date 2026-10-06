from pathlib import Path
from egai_v22.core.canonical import sha256_bytes, sha256_obj

def runtime_closure_digest(root):
    root=Path(root); entries=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            entries.append((str(p.relative_to(root)),sha256_bytes(p.read_bytes())))
    return sha256_obj(entries)
