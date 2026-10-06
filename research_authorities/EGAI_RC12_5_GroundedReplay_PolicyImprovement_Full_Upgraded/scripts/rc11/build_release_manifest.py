#!/usr/bin/env python3
"""Build deterministic RC11 release manifest v3.

v3 binds bytes, SHA-256, and POSIX mode bits. Symlinks are forbidden in the
release tree because a hash of the dereferenced target is not a safe package
identity.
"""
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

def record(path: Path, root: Path) -> dict:
    if path.is_symlink():
        raise ValueError(f"release tree contains forbidden symlink: {path.relative_to(root)}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "mode": format(stat.S_IMODE(path.stat().st_mode), "04o"),
        "sha256": h.hexdigest(),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    version = args.version or (root / "VERSION").read_text().strip()
    paths=[]
    for p in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not include(p, root):
            continue
        if p.is_symlink():
            raise SystemExit(f"forbidden symlink in release tree: {p.relative_to(root)}")
        if p.is_file():
            paths.append(p)
    files = [record(p, root) for p in paths]
    tree = "sha256:" + hashlib.sha256(canonical(files)).hexdigest()
    payload = {
        "schema_version": 3,
        "release": "RC11 Coherent Hybrid Continual Runtime",
        "version": version,
        "target": "macOS Apple Silicon + retained portable host/reference layers",
        "file_count": len(files),
        "release_tree_sha256": tree,
        "files": files,
    }
    out = root / MANIFEST_NAME
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"wrote {out} ({len(files)} files, {tree})")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
