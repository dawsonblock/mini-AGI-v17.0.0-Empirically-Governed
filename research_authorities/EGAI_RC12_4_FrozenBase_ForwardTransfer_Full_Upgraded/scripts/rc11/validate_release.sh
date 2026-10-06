#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
"$ROOT/scripts/rc11/validate_all.sh"
python3 -m compileall -q "$ROOT/runtime/src" "$ROOT/scripts/rc11"
for f in "$ROOT/scripts/rc11"/*.sh; do bash -n "$f"; done
python3 "$ROOT/scripts/rc11/verify_release.py" --root "$ROOT"
python3 "$ROOT/scripts/rc11/macos_qualification.py" --allow-non-macos-probe >/dev/null
echo 'RC11.6 release validation passed.'
