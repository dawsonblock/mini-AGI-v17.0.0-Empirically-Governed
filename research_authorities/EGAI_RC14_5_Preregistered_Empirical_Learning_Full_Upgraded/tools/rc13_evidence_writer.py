#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from minagi.egai.canonical import sha256_json
from minagi.egai.evidence import EvidenceLedger, TrustedEvidenceIngestor
from minagi.egai.models import EvidenceOrigin


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('index', type=int)
    ns=ap.parse_args()
    ledger=EvidenceLedger(ns.root)
    ingestor=TrustedEvidenceIngestor(ledger, ingestor_id=f'writer-{ns.index}')
    r=ingestor.ingest(
        {'writer':ns.index,'value':f'payload-{ns.index}'},
        origin_class=EvidenceOrigin.ENVIRONMENT,
        production_identity_digest=sha256_json({'runtime':'rc13'}),
        provenance={'worker':ns.index},
    )
    print(json.dumps({'index':ns.index,'digest':r.digest},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
