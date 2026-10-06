#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/runtime"
PYTHONPATH=src:tests/governance python -m pytest -q tests/continual tests/execution tests/governance tests/governance_integration
PYTHONPATH=src python -m compileall -q src
