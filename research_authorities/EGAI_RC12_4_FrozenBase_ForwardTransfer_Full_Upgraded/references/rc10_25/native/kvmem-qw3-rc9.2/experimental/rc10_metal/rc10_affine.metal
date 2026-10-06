#include <metal_stdlib>
using namespace metal;

// Reference RC10 affine primitive for Apple GPU qualification.
// Row-major square matrices. This is intentionally a correctness primitive,
// not a fused production Gated DeltaNet kernel.
kernel void rc10_affine_left(
    device const float* T [[buffer(0)]],
    device const float* S [[buffer(1)]],
    device const float* Z [[buffer(2)]],
    device float* O [[buffer(3)]],
    constant uint& n [[buffer(4)]],
    uint2 gid [[thread_position_in_grid]]) {
    const uint row = gid.y;
    const uint col = gid.x;
    if (row >= n || col >= n) return;
    float acc = 0.0f;
    for (uint k = 0; k < n; ++k) {
        acc += T[row*n + k] * S[k*n + col];
    }
    O[row*n + col] = acc + Z[row*n + col];
}

kernel void rc10_affine_right(
    device const float* T [[buffer(0)]],
    device const float* S [[buffer(1)]],
    device const float* Z [[buffer(2)]],
    device float* O [[buffer(3)]],
    constant uint& n [[buffer(4)]],
    uint2 gid [[thread_position_in_grid]]) {
    const uint row = gid.y;
    const uint col = gid.x;
    if (row >= n || col >= n) return;
    float acc = 0.0f;
    for (uint k = 0; k < n; ++k) {
        acc += S[row*n + k] * T[k*n + col];
    }
    O[row*n + col] = acc + Z[row*n + col];
}
