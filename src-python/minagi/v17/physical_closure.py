from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
from minagi.integration.qw3_state import ServedArtifactManifest, RuntimeStateMismatch, canonical_digest
from minagi.v15.runtime_closure import sha256_file, sha256_runtime_path, tokenizer_identity_sha256_v155

ZERO_ROOT = "0" * 64

@dataclass(frozen=True)
class PhysicalArtifactPathsV17:
    adapter_set_artifact: str | None = None
    retrieval_policy_artifact: str | None = None
    skill_policy_artifact: str | None = None


def _measure(path: str | None, expected: str, label: str) -> str:
    if expected == ZERO_ROOT:
        if path is not None:
            raise RuntimeStateMismatch(f"{label}: path supplied for zero root")
        return ZERO_ROOT
    if path is None:
        raise RuntimeStateMismatch(f"{label}: physical artifact required")
    measured = sha256_runtime_path(path)
    if measured != expected:
        raise RuntimeStateMismatch(f"{label}: physical bytes do not match authorized root")
    return measured

@dataclass(frozen=True)
class MeasuredRuntimeClosureV17:
    epoch_id: str
    manifest_digest: str
    artifact_root: str
    foundation_digest: str
    tokenizer_digest: str
    runtime_binary_digest: str
    kvmem_archive_root: str
    adapter_set_root: str
    retrieval_policy_root: str
    skill_policy_root: str
    native_adapter_bundle_root: str
    schema: str = "mini-agi-v17-runtime-closure"

    @property
    def digest(self) -> str:
        return canonical_digest(asdict(self))

    @classmethod
    def from_files(cls, *, manifest: ServedArtifactManifest, model_path: str | Path,
                   runtime_binary_path: str | Path, kvmem_archive_dir: str | Path | None = None,
                   artifacts: PhysicalArtifactPathsV17 | None = None) -> "MeasuredRuntimeClosureV17":
        artifacts = artifacts or PhysicalArtifactPathsV17()
        foundation = sha256_runtime_path(model_path)
        tokenizer = tokenizer_identity_sha256_v155(model_path)
        runtime = sha256_file(runtime_binary_path)
        kv = ZERO_ROOT if kvmem_archive_dir is None else sha256_file(Path(kvmem_archive_dir) / "manifest.json")
        measured = (foundation, tokenizer, runtime, kv)
        expected = (manifest.foundation_digest, manifest.tokenizer_digest, manifest.runtime_binary_digest, manifest.kv_archive_root)
        if measured != expected:
            labels = ("foundation", "tokenizer", "runtime", "kvmem")
            raise RuntimeStateMismatch("v17 physical closure mismatch: " + ", ".join(n for n,a,e in zip(labels, measured, expected) if a != e))
        adapter = _measure(artifacts.adapter_set_artifact, manifest.adapter_set_root, "adapter_set")
        retrieval = _measure(artifacts.retrieval_policy_artifact, manifest.retrieval_policy_root, "retrieval_policy")
        skill = _measure(artifacts.skill_policy_artifact, manifest.skill_policy_root, "skill_policy")
        return cls(manifest.epoch_digest, manifest.manifest_digest, manifest.artifact_root,
                   foundation, tokenizer, runtime, kv, adapter, retrieval, skill,
                   manifest.native_adapter_bundle_root)
