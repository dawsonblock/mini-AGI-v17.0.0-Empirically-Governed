#!/usr/bin/env python3
"""Verify RC11 release tree against manifest v3."""
from __future__ import annotations
import argparse, hashlib, json, stat
from pathlib import Path

EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache", "build", "dist"}
MANIFEST_NAME = "RC11_RELEASE_MANIFEST.json"

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()

def include(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if rel.as_posix() == MANIFEST_NAME:
        return False
    return not any(part in EXCLUDED_PARTS for part in rel.parts)

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--root', default=str(Path(__file__).resolve().parents[2])); a=ap.parse_args()
    root=Path(a.root).resolve(); manifest=json.loads((root/MANIFEST_NAME).read_text())
    if manifest.get('schema_version') != 3:
        raise SystemExit('unsupported release manifest schema (RC11 requires v3)')
    expected={r['path']:r for r in manifest['files']}
    actual_paths={}
    symlinks=[]
    for p in root.rglob('*'):
        if not include(p, root): continue
        if p.is_symlink():
            symlinks.append(p.relative_to(root).as_posix()); continue
        if p.is_file(): actual_paths[p.relative_to(root).as_posix()]=p
    missing=sorted(set(expected)-set(actual_paths)); extra=sorted(set(actual_paths)-set(expected)); changed=[]; mode_changed=[]
    for rel in sorted(set(expected)&set(actual_paths)):
        p=actual_paths[rel]; r=expected[rel]
        if p.stat().st_size != r['bytes'] or digest(p) != r['sha256']: changed.append(rel)
        actual_mode=format(stat.S_IMODE(p.stat().st_mode),'04o')
        if actual_mode != r.get('mode'): mode_changed.append(rel)
    ordered=[expected[k] for k in sorted(expected)]
    tree='sha256:'+hashlib.sha256(canonical(ordered)).hexdigest(); tree_ok=tree==manifest.get('release_tree_sha256')
    ok=not (missing or extra or changed or mode_changed or symlinks) and tree_ok
    out={'ok':ok,'version':manifest.get('version'),'files':len(expected),'release_tree_sha256':tree,'missing':missing,'extra':extra,'changed':changed,'mode_changed':mode_changed,'symlinks':sorted(symlinks),'tree_ok':tree_ok}
    print(json.dumps(out,indent=2,sort_keys=True)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
