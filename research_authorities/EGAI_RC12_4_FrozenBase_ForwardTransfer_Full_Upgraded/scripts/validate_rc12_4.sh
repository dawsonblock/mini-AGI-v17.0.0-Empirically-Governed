#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/runtime"
python -m pytest -q
python -m compileall -q src
python -m pip wheel . --no-deps --no-build-isolation -w dist
python - <<'PY'
from pathlib import Path
from kvcontinual.governance.source_closure import write_source_closure,verify_source_closure
root=Path.cwd().parent
out=root/'release/RC12_4_FROZEN_TRANSFER_SOURCE_CLOSURE.json'
c=write_source_closure(root,out,'12.4.0')
assert verify_source_closure(root,out)
print(c.closure_digest,len(c.files))
PY
