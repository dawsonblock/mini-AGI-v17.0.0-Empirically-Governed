#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from kvcontinual.registry import AdapterRegistry

p=argparse.ArgumentParser(description="Audit RC10.24 production pointer and hash-chained promotion WAL.")
p.add_argument('--registry', required=True)
a=p.parse_args()
r=AdapterRegistry(a.registry)
state=r.audit_production_state()
print(json.dumps({"ok":True,"production":state,"wal_head":r.promotion_wal.head_digest}, indent=2, sort_keys=True))
