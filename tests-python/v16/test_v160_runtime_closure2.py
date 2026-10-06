from pathlib import Path

import pytest

from minagi.integration.qw3_state import QW3RuntimeState, ServedArtifactManifest
from minagi.v15.runtime_closure import sha256_file, sha256_runtime_path
from minagi.v16.runtime_closure2 import MeasuredRuntimeClosureV2, FullMeasuredGovernedServingContract


def _digest(p): return sha256_runtime_path(p)


def test_runtime_closure2_measures_tokenizer_retrieval_and_skill(tmp_path):
    model=tmp_path/'model.bin'; model.write_bytes(b'model')
    tok=tmp_path/'tok.json'; tok.write_bytes(b'tokenizer')
    exe=tmp_path/'qw3'; exe.write_bytes(b'executable')
    retrieval=tmp_path/'retrieval.json'; retrieval.write_bytes(b'retrieval')
    skill=tmp_path/'skill.json'; skill.write_bytes(b'skill')
    m=ServedArtifactManifest(
        epoch_digest='sha256:'+'a'*64,runtime_manifest_digest='sha256:'+'b'*64,
        foundation_digest=_digest(model),tokenizer_digest=_digest(tok),kv_archive_root='0'*64,
        adapter_set_root='1'*64,retrieval_policy_root=_digest(retrieval),skill_policy_root=_digest(skill),
        runtime_binary_digest=sha256_file(exe),
    )
    c=MeasuredRuntimeClosureV2.from_files(manifest=m,model_path=model,tokenizer_path=tok,runtime_binary_path=exe,retrieval_policy_path=retrieval,skill_policy_path=skill)
    assert c.tokenizer_digest==m.tokenizer_digest and c.retrieval_policy_root==m.retrieval_policy_root and c.skill_policy_root==m.skill_policy_root
    tok.write_bytes(b'tampered')
    with pytest.raises(PermissionError):
        MeasuredRuntimeClosureV2.from_files(manifest=m,model_path=model,tokenizer_path=tok,runtime_binary_path=exe,retrieval_policy_path=retrieval,skill_policy_path=skill)


def test_full_measured_contract_rejects_missing_native_v2_measurements():
    class Lease: epoch_digest='sha256:'+'a'*64
    m=ServedArtifactManifest(
        epoch_digest=Lease.epoch_digest,runtime_manifest_digest='sha256:'+'b'*64,
        foundation_digest='1'*64,tokenizer_digest='2'*64,kv_archive_root='0'*64,adapter_set_root='4'*64,
        retrieval_policy_root='5'*64,skill_policy_root='6'*64,runtime_binary_digest='7'*64,
    )
    state={
        'governed':True,'epoch_id':m.epoch_digest,'manifest_digest':m.manifest_digest,'artifact_root':m.artifact_root,'adapter_set_root':m.adapter_set_root,
        'runtime_closure_verified':True,'runtime_closure_digest':'deadbeef','measured_foundation_digest':m.foundation_digest,
        'measured_runtime_binary_digest':m.runtime_binary_digest,'measured_kvmem_archive_root':m.kv_archive_root,
        'measured_tokenizer_digest':None,'measured_retrieval_policy_root':None,'measured_skill_policy_root':None,
    }
    c=FullMeasuredGovernedServingContract(base_url='http://invalid',fetch_json=lambda path:state)
    with pytest.raises(PermissionError): c.verify_loaded_state(lease=Lease(),manifest=m)
