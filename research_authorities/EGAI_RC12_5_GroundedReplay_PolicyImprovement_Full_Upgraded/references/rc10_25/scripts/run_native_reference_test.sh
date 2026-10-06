#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
D="$ROOT/native/kvmem-qw3-rc9.2/experimental/rc10"
CXX_BIN="${CXX:-}"
if [[ -z "$CXX_BIN" ]]; then
  if command -v clang++ >/dev/null 2>&1; then CXX_BIN=clang++; else CXX_BIN=g++; fi
fi
"$CXX_BIN" -std=c++17 "$D/affine_reference_test.cpp" -I"$D" -o /tmp/rc10_affine_test
/tmp/rc10_affine_test
