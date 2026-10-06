#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from kvcontinual.hardware_qualification import (
    QualificationSuiteCase,
    build_qualification_suite_manifest,
    qualification_payload_digest,
)

p=argparse.ArgumentParser(description='Build an RC10.24 content-bound qualification suite manifest from JSON cases.')
p.add_argument('--cases-json',required=True,help='JSON array with case_id,payload,topology?,segment_count?')
p.add_argument('--name',default='rc10-macos-qwen-qualification')
p.add_argument('--out',required=True)
a=p.parse_args()
raw=json.loads(Path(a.cases_json).read_text(encoding='utf-8'))
cases=[]
for item in raw:
    cases.append(QualificationSuiteCase(
        case_id=str(item['case_id']),
        payload_digest=qualification_payload_digest(item['payload']),
        topology=str(item.get('topology','ARBITRARY')),
        segment_count=int(item.get('segment_count',0)),
    ))
manifest=build_qualification_suite_manifest(a.name,cases)
Path(a.out).write_text(json.dumps(manifest.to_dict(),indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'suite_manifest':a.out,'suite_digest':manifest.suite_digest,'case_count':len(cases)},indent=2,sort_keys=True))
