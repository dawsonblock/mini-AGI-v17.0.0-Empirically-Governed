#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from kvcontinual.deployment_binding import AccelerationDeploymentBinding
from kvcontinual.hardware_qualification import AccelerationQualificationCertificate

p=argparse.ArgumentParser(description='Verify an RC10.24 deployment binding against its qualification certificate.')
p.add_argument('binding')
p.add_argument('certificate')
a=p.parse_args()
binding=AccelerationDeploymentBinding.from_dict(json.loads(Path(a.binding).read_text(encoding='utf-8')))
cert=AccelerationQualificationCertificate.from_dict(json.loads(Path(a.certificate).read_text(encoding='utf-8')))
binding.validate_certificate(cert)
print(binding.binding_digest)
