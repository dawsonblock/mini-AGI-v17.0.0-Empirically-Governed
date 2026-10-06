#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/.venv/bin/activate"
export PYTORCH_ENABLE_MPS_FALLBACK=1
python -m pytest -q
python -m kvcontinual.cli mac-diagnose
python -m kvcontinual.cli mac-affine-demo
python -m kvcontinual.cli mac-gdn-demo
