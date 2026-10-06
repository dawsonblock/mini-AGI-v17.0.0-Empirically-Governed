#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"

echo '== RC11.7 unified Python runtime =='
(cd "$ROOT/runtime" && PYTHONPATH=src "$PYTHON" -m pytest -q tests)

echo '== mini-AGI authority/control reference regression =='
(cd "$ROOT/authority" && PYTHONPATH=. "$PYTHON" -m pytest -q tests)

echo '== Qwen/RC10 oracle reference regression =='
(cd "$ROOT/oracle_reference" && PYTHONPATH=. "$PYTHON" -m pytest -q tests)

echo 'All RC11.7 Python/reference suites passed.'
