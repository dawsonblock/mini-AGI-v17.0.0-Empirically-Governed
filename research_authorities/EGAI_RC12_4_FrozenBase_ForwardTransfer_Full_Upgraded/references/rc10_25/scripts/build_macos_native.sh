#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NATIVE="$ROOT/native/kvmem-qw3-rc9.2"
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then echo "ERROR: Apple Silicon macOS required" >&2; exit 2; fi
command -v cmake >/dev/null || { echo "ERROR: cmake required (brew install cmake)" >&2; exit 3; }
command -v xcrun >/dev/null || { echo "ERROR: Xcode Command Line Tools required (xcode-select --install)" >&2; exit 4; }
cmake --preset macos-arm64-host -S "$NATIVE"
cmake --build --preset macos-arm64-host
ctest --preset macos-arm64-host --test-dir "$NATIVE/build/macos-arm64-host"
METAL="$NATIVE/experimental/rc10_metal"
mkdir -p "$METAL/build"
xcrun -sdk macosx metal -c "$METAL/rc10_affine.metal" -o "$METAL/build/rc10_affine.air"
xcrun -sdk macosx metal -c "$METAL/rc10_gdn_reference.metal" -o "$METAL/build/rc10_gdn_reference.air"
xcrun -sdk macosx metallib "$METAL/build/rc10_affine.air" "$METAL/build/rc10_gdn_reference.air" -o "$METAL/build/rc10_reference.metallib"
clang++ -std=c++17 -fobjc-arc "$METAL/metal_affine_smoke.mm" -framework Foundation -framework Metal -o "$METAL/build/metal_affine_smoke"
clang++ -std=c++17 -fobjc-arc "$METAL/metal_gdn_smoke.mm" -framework Foundation -framework Metal -o "$METAL/build/metal_gdn_smoke"
clang++ -std=c++17 -fobjc-arc "$METAL/metal_conv_smoke.mm" -framework Foundation -framework Metal -o "$METAL/build/metal_conv_smoke"
"$METAL/build/metal_affine_smoke" "$METAL/build/rc10_reference.metallib"
"$METAL/build/metal_gdn_smoke" "$METAL/build/rc10_reference.metallib"
"$METAL/build/metal_conv_smoke" "$METAL/build/rc10_reference.metallib"
echo "macOS host + Metal affine + GDN/HYPIC + causal-conv seam reference validation complete"
