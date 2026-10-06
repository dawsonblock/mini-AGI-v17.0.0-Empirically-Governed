from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from minagi.integration.qw3_state import (
    GovernedServingContract,
    QW3RuntimeState,
    RuntimeStateMismatch,
    ServedArtifactManifest,
    canonical_digest,
)
from minagi.v15.runtime_closure import MeasuredGovernedServingContract, sha256_file, sha256_runtime_path

_ZERO_ROOT = "0" * 64


@dataclass(frozen=True)
class MeasuredRuntimeClosureV2:
    """RuntimeClosure2: all served roots that can be represented as files are measured.

    v15.4 measured model, executable and KVMem manifest while tokenizer,
    retrieval-policy and skill-policy identities were launcher supplied.  V2
    requires concrete paths for those artifacts and derives their roots from
    bytes before QW3 is launched.  The companion native QW3 changes included in
    this repository repeat those three measurements when the new path flags are
    supplied.
    """

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
    schema: str = "mini-agi-v16-runtime-closure-v2"

    @property
    def digest(self) -> str:
        return canonical_digest(asdict(self))

    @classmethod
    def from_files(
        cls,
        *,
        manifest: ServedArtifactManifest,
        model_path: str | Path,
        tokenizer_path: str | Path,
        runtime_binary_path: str | Path,
        retrieval_policy_path: str | Path,
        skill_policy_path: str | Path,
        kvmem_archive_dir: str | Path | None = None,
    ) -> "MeasuredRuntimeClosureV2":
        model_sha = sha256_runtime_path(model_path)
        tok_sha = sha256_runtime_path(tokenizer_path)
        runtime_sha = sha256_file(runtime_binary_path)
        retrieval_sha = sha256_runtime_path(retrieval_policy_path)
        skill_sha = sha256_runtime_path(skill_policy_path)
        if kvmem_archive_dir is None:
            kv_root = _ZERO_ROOT
        else:
            kv_root = sha256_file(Path(kvmem_archive_dir) / "manifest.json")
        expected = (
            manifest.foundation_digest,
            manifest.tokenizer_digest,
            manifest.runtime_binary_digest,
            manifest.kv_archive_root,
            manifest.retrieval_policy_root,
            manifest.skill_policy_root,
        )
        actual = (model_sha, tok_sha, runtime_sha, kv_root, retrieval_sha, skill_sha)
        if actual != expected:
            labels = (
                "foundation_digest",
                "tokenizer_digest",
                "runtime_binary_digest",
                "kv_archive_root",
                "retrieval_policy_root",
                "skill_policy_root",
            )
            bad = [name for name, a, e in zip(labels, actual, expected) if a != e]
            raise RuntimeStateMismatch("RuntimeClosure2 measured mismatch: " + ", ".join(bad))
        return cls(
            epoch_id=manifest.epoch_digest,
            manifest_digest=manifest.manifest_digest,
            artifact_root=manifest.artifact_root,
            foundation_digest=model_sha,
            tokenizer_digest=tok_sha,
            runtime_binary_digest=runtime_sha,
            kvmem_archive_root=kv_root,
            adapter_set_root=manifest.adapter_set_root,
            retrieval_policy_root=retrieval_sha,
            skill_policy_root=skill_sha,
            native_adapter_bundle_root=manifest.native_adapter_bundle_root,
        )

    def qw3_args(self, *, manifest: ServedArtifactManifest, tokenizer_path: str | Path,
                 retrieval_policy_path: str | Path, skill_policy_path: str | Path) -> tuple[str, ...]:
        if self.epoch_id != manifest.epoch_digest or self.manifest_digest != manifest.manifest_digest or self.artifact_root != manifest.artifact_root:
            raise RuntimeStateMismatch("RuntimeClosure2 does not match served manifest")
        args = [
            "--state-epoch-id", manifest.epoch_digest,
            "--state-manifest-digest", manifest.manifest_digest,
            "--state-artifact-root", manifest.artifact_root,
            "--state-adapter-set-root", manifest.adapter_set_root,
            "--state-foundation-digest", manifest.foundation_digest,
            "--state-tokenizer-digest", manifest.tokenizer_digest,
            "--state-tokenizer-path", str(Path(tokenizer_path)),
            "--state-kvmem-archive-root", manifest.kv_archive_root,
            "--state-retrieval-policy-root", manifest.retrieval_policy_root,
            "--state-retrieval-policy-path", str(Path(retrieval_policy_path)),
            "--state-skill-policy-root", manifest.skill_policy_root,
            "--state-skill-policy-path", str(Path(skill_policy_path)),
            "--state-runtime-binary-digest", manifest.runtime_binary_digest,
        ]
        if manifest.native_adapter_bundle_root != _ZERO_ROOT:
            args += ["--state-native-adapter-bundle-root", manifest.native_adapter_bundle_root]
        return tuple(args)


class FullMeasuredGovernedServingContract(MeasuredGovernedServingContract):
    """Require the QW3 RuntimeClosure2 measurements, not only RuntimeClosure1."""

    def verify_loaded_state(self, *, lease, manifest: ServedArtifactManifest) -> QW3RuntimeState:
        # Skip the v15.4 closure-digest comparison: RuntimeClosure2 deliberately
        # uses a different digest schema containing the newly measured roots.
        state = GovernedServingContract.verify_loaded_state(self, lease=lease, manifest=manifest)
        if not state.runtime_closure_verified:
            raise RuntimeStateMismatch("QW3 has not verified measured runtime closure")
        required = {
            "measured_foundation_digest": manifest.foundation_digest,
            "measured_runtime_binary_digest": manifest.runtime_binary_digest,
            "measured_kvmem_archive_root": manifest.kv_archive_root,
            "measured_tokenizer_digest": manifest.tokenizer_digest,
            "measured_retrieval_policy_root": manifest.retrieval_policy_root,
            "measured_skill_policy_root": manifest.skill_policy_root,
        }
        for name, expected in required.items():
            actual = getattr(state, name, None)
            if actual != expected:
                raise RuntimeStateMismatch(f"QW3 RuntimeClosure2 {name} mismatch: expected {expected} got {actual!r}")
        expected_closure = MeasuredRuntimeClosureV2(
            epoch_id=manifest.epoch_digest,
            manifest_digest=manifest.manifest_digest,
            artifact_root=manifest.artifact_root,
            foundation_digest=manifest.foundation_digest,
            tokenizer_digest=manifest.tokenizer_digest,
            runtime_binary_digest=manifest.runtime_binary_digest,
            kvmem_archive_root=manifest.kv_archive_root,
            adapter_set_root=manifest.adapter_set_root,
            retrieval_policy_root=manifest.retrieval_policy_root,
            skill_policy_root=manifest.skill_policy_root,
            native_adapter_bundle_root=manifest.native_adapter_bundle_root,
        )
        if state.runtime_closure_digest != expected_closure.digest:
            raise RuntimeStateMismatch(
                f"QW3 RuntimeClosure2 digest mismatch: expected {expected_closure.digest} got {state.runtime_closure_digest!r}"
            )
        return state
