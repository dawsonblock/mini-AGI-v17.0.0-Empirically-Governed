#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
GENERATED_PARTS = {"__pycache__", ".pytest_cache", "build", "dist", ".git"}
GENERATED_SUFFIXES = {".pyc", ".pyo", ".o", ".a", ".so", ".dylib", ".whl"}
MODEL_SUFFIXES = {".gguf", ".safetensors", ".ckpt", ".pt", ".pth"}


def problem(out: list[str], message: str) -> None:
    out.append(message)


def main() -> int:
    problems: list[str] = []
    required = [
        "VERSION", "pyproject.toml", "README.md", "SOURCE_PROVENANCE.json",
        "RELEASE_VALIDATION.json", "VALIDATION_SUMMARY.md", "SBOM.cdx.json",
        "docs/RC13_3_1_RELEASE_NOTES.md", "docs/PRODUCTION_LIMITS.md",
        "src-python/minagi/system.py", "src-python/minagi/state_epoch.py",
        "src-python/minagi/egai/evidence.py", "src-python/minagi/egai/skills.py",
        "src-python/minagi/egai/beliefs.py",
        "src-python/kvcontinual/execution/activation.py",
        "src-python/kvcontinual/execution/governed_manifest.py",
        "src-python/kvcontinual/execution/durability/control_state.py",
        "src-python/kvcontinual/execution/durability/file_lock.py",
        "tests-python/test_rc13_transactional_hardening.py",
    ]
    for rel in required:
        if not (ROOT / rel).is_file():
            problem(problems, f"missing required RC13.3.1 file: {rel}")

    try:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        version = str(metadata["version"])
        if version != (ROOT / "VERSION").read_text(encoding="utf-8").strip():
            problem(problems, "pyproject/VERSION mismatch")
        if metadata.get("scripts", {}).get("egai") != "minagi.cli:main":
            problem(problems, "canonical egai CLI is not minagi.cli:main")
        if metadata.get("scripts", {}).get("egai-research") != "egai.cli:main":
            problem(problems, "legacy research CLI is not explicitly separated")
    except Exception as exc:
        problem(problems, f"invalid pyproject/version metadata: {exc}")
        version = ""

    version_files = [
        "src-python/minagi/__init__.py", "src-python/kvcontinual/__init__.py",
        "src-python/kvcontinual/_version.py", "src-python/kvcontinual/execution/__init__.py",
        "src-python/kvcontinual/continual/__init__.py",
    ]
    for rel in version_files:
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
            if not m or m.group(1) != version:
                problem(problems, f"version mismatch in {rel}")
        except Exception as exc:
            problem(problems, f"cannot inspect version in {rel}: {exc}")

    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in GENERATED_PARTS or part.endswith(".egg-info") for part in rel.parts):
            problem(problems, f"generated/cache material present: {rel}")
        if p.suffix in GENERATED_SUFFIXES:
            problem(problems, f"compiled/generated file present: {rel}")
        if p.suffix.lower() in MODEL_SUFFIXES:
            problem(problems, f"model/checkpoint bytes must not ship in source release: {rel}")
        if p.suffix.lower() in {".pem", ".p12", ".key"} and rel.as_posix() != "RELEASE_PUBLIC_KEY.pem":
            problem(problems, f"private/credential-shaped file present: {rel}")

    # Production code must never import reference trees.
    for base in (ROOT / "src-python" / "minagi", ROOT / "src-python" / "kvcontinual", ROOT / "src-python" / "egai"):
        for p in base.rglob("*.py"):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except Exception as exc:
                problem(problems, f"Python syntax failure {p.relative_to(ROOT)}: {exc}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(n == "reference" or n.startswith("reference.") or n == "references" or n.startswith("references.") for n in names):
                    problem(problems, f"production imports reference tree: {p.relative_to(ROOT)}")

    try:
        provenance = json.loads((ROOT / "SOURCE_PROVENANCE.json").read_text(encoding="utf-8"))
        if provenance.get("release") != version:
            problem(problems, "SOURCE_PROVENANCE release/version mismatch")
        if "trunk" not in provenance or not provenance.get("integrated_donors"):
            problem(problems, "SOURCE_PROVENANCE lacks trunk/donor closure")
    except Exception as exc:
        problem(problems, f"invalid SOURCE_PROVENANCE.json: {exc}")

    current_text = "\n".join((ROOT / x).read_text(encoding="utf-8") for x in ["README.md", "docs/RC13_3_1_RELEASE_NOTES.md"])
    if "RC11.7 as the sole execution substrate" in current_text:
        problem(problems, "current release documentation still claims RC11.7-only execution governance")

    if problems:
        print("RC13.3.1 source audit: FAIL", file=sys.stderr)
        for item in problems:
            print(" - " + item, file=sys.stderr)
        return 1
    print(f"RC13.3.1 source audit: PASS ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
