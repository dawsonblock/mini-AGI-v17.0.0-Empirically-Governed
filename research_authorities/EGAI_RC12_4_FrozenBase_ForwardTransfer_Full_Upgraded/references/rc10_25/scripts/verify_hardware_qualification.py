#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from kvcontinual.hardware_qualification import AccelerationQualificationCertificate
from kvcontinual.types import ExecutionIdentity, ModelIdentity

p=argparse.ArgumentParser(description="Verify an RC10.24 hardware acceleration certificate.")
p.add_argument("certificate")
p.add_argument("identity_json")
p.add_argument("--backend-fingerprint", required=True)
p.add_argument("--hardware-runtime-digest", required=True)
p.add_argument("--release-manifest-digest", required=True)
p.add_argument("--ledger-head")
a=p.parse_args()
raw=json.loads(Path(a.identity_json).read_text())
m=raw["model"]
identity=ExecutionIdentity(ModelIdentity(**m), raw["kernel_abi"], raw["recurrence_impl"], raw["tensor_layout"], raw["activation_dtype"], raw["cache_dtype"], raw.get("runtime_learning_state","frozen"))
cert=AccelerationQualificationCertificate.from_dict(json.loads(Path(a.certificate).read_text()))
cert.validate(identity=identity,backend_fingerprint=a.backend_fingerprint,hardware_runtime_digest=a.hardware_runtime_digest,release_manifest_digest=a.release_manifest_digest,qualification_suite_digest=a.qualification_suite_digest,qualification_ledger_head=a.ledger_head)
print(cert.certificate_digest)
