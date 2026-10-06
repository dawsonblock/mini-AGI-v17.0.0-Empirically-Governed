#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from kvcontinual.hardware_qualification import (
    AccelerationQualificationObservation,
    AccelerationQualificationThresholds,
    HardwareQualificationStore,
    QualificationSuiteManifest,
    build_acceleration_qualification_certificate,
    detect_hardware_runtime_fingerprint,
)
from kvcontinual.qualification_ledger import QualificationLedger
from kvcontinual.types import ExecutionIdentity, ModelIdentity


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return 'sha256:'+h.hexdigest()


def load_identity(path: Path) -> ExecutionIdentity:
    raw=json.loads(path.read_text())
    m=raw['model']
    return ExecutionIdentity(ModelIdentity(**m),raw['kernel_abi'],raw['recurrence_impl'],raw['tensor_layout'],raw['activation_dtype'],raw['cache_dtype'],raw.get('runtime_learning_state','frozen'))

p=argparse.ArgumentParser(description='Build an RC10.24 Apple-Silicon acceleration qualification certificate from paired exact/accelerated observations.')
p.add_argument('--identity-json',required=True)
p.add_argument('--backend-fingerprint',required=True)
p.add_argument('--release-manifest',default='BUILD_MANIFEST.json')
p.add_argument('--observations-json',required=True,help='JSON array of AccelerationQualificationObservation objects')
p.add_argument('--suite-manifest',required=True,help='RC10.24 content-bound qualification suite manifest')
p.add_argument('--ledger',required=True)
p.add_argument('--store',required=True)
p.add_argument('--min-cases',type=int,default=100)
p.add_argument('--max-logit-kl',type=float,default=0.02)
p.add_argument('--min-top1',type=float,default=0.995)
p.add_argument('--max-failure-rate',type=float,default=0.01)
p.add_argument('--min-median-ttft-speedup',type=float,default=1.0)
a=p.parse_args()
identity=load_identity(Path(a.identity_json))
obs=[AccelerationQualificationObservation(**x) for x in json.loads(Path(a.observations_json).read_text())]
suite=QualificationSuiteManifest.from_dict(json.loads(Path(a.suite_manifest).read_text(encoding='utf-8')))
suite.validate_observations(obs)
ledger=QualificationLedger(a.ledger); ledger_head=ledger.head_digest
hw=detect_hardware_runtime_fingerprint(backend_fingerprint=a.backend_fingerprint)
thresholds=AccelerationQualificationThresholds(a.max_logit_kl,a.min_top1,a.max_failure_rate,a.min_cases,a.min_median_ttft_speedup)
cert=build_acceleration_qualification_certificate(identity=identity,backend_fingerprint=a.backend_fingerprint,hardware_runtime=hw,release_manifest_digest=sha256_file(Path(a.release_manifest)),observations=obs,qualification_suite=suite,qualification_ledger_head=ledger_head,thresholds=thresholds)
path=HardwareQualificationStore(a.store).put(cert)
print(json.dumps({'certificate':str(path),'certificate_digest':cert.certificate_digest,'passed':cert.summary.passed,'hardware_runtime_digest':hw.digest,'release_manifest_digest':cert.release_manifest_digest,'ledger_head':ledger_head,'qualification_suite_digest':suite.suite_digest},indent=2,sort_keys=True))
if not cert.summary.passed:
    raise SystemExit(2)
