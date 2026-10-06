#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from kvcontinual.deployment_binding import build_deployment_binding
from kvcontinual.hardware_qualification import (
    AccelerationQualificationCertificate,
    QualificationSuiteManifest,
    detect_hardware_runtime_fingerprint,
)
from kvcontinual.qualification_ledger import QualificationLedger


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return 'sha256:'+h.hexdigest()

p=argparse.ArgumentParser(description='Create an RC10.24 target-host deployment binding from a passing qualification certificate.')
p.add_argument('--certificate',required=True)
p.add_argument('--backend-fingerprint',required=True)
p.add_argument('--release-manifest',default='BUILD_MANIFEST.json')
p.add_argument('--suite-manifest',required=True)
p.add_argument('--ledger',required=True)
p.add_argument('--out',required=True)
a=p.parse_args()
cert=AccelerationQualificationCertificate.from_dict(json.loads(Path(a.certificate).read_text(encoding='utf-8')))
suite=QualificationSuiteManifest.from_dict(json.loads(Path(a.suite_manifest).read_text(encoding='utf-8')))
if not suite.reusable: raise SystemExit('qualification suite manifest is invalid')
hw=detect_hardware_runtime_fingerprint(backend_fingerprint=a.backend_fingerprint)
ledger_head=QualificationLedger(a.ledger).head_digest
binding=build_deployment_binding(
    cert,
    backend_fingerprint=a.backend_fingerprint,
    hardware_runtime_digest=hw.digest,
    release_manifest_digest=sha256_file(Path(a.release_manifest)),
    qualification_ledger_head=ledger_head,
    qualification_suite_digest=suite.suite_digest,
)
Path(a.out).write_text(json.dumps(binding.to_dict(),indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'deployment_binding':a.out,'binding_digest':binding.binding_digest,'certificate_digest':binding.certificate_digest},indent=2,sort_keys=True))
