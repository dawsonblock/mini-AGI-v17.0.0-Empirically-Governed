#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != "Darwin" ]]; then echo "ERROR: macOS required" >&2; exit 2; fi
if [[ "$(uname -m)" != "arm64" ]]; then echo "ERROR: native Apple Silicon arm64 shell required; do not run under Rosetta" >&2; exit 3; fi
command -v python3 >/dev/null || { echo "ERROR: python3 is required" >&2; exit 4; }
python3 -m venv "$ROOT/.venv"
source "$ROOT/.venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$ROOT[macos,dev]"
if [[ "${RC10_INSTALL_MLX:-1}" == "1" ]]; then python -m pip install -e "$ROOT[mlx]"; fi
printf '\nInstalled RC10.24 macOS environment.\n'
python -m kvcontinual.cli mac-diagnose
