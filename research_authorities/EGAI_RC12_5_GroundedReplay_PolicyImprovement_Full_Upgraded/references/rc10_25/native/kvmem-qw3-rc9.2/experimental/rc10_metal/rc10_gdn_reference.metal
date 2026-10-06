#include <metal_stdlib>
using namespace metal;

// Correctness-first Gated DeltaNet/HYPIC primitives for Apple GPU bring-up.
// These kernels are deliberately simple and are NOT the final fused production
// implementation. The Mac/Qwen path follows current Hugging Face Qwen3.5
// repeat-interleave key-head semantics; the bundled RC9.2 CUDA path retains its
// historical modulo layout and is not silently treated as equivalent.

kernel void rc10_gdn_prepare(
    device const float* alpha_raw [[buffer(0)]],
    device const float* beta_raw  [[buffer(1)]],
    device const float* dt_bias   [[buffer(2)]],
    device const float* ssm_a     [[buffer(3)]],
    device float* decay_out       [[buffer(4)]],
    device float* beta_out        [[buffer(5)]],
    constant uint& token_count    [[buffer(6)]],
    constant uint& num_v_heads    [[buffer(7)]],
    uint gid [[thread_position_in_grid]]) {
    const uint total = token_count * num_v_heads;
    if (gid >= total) return;
    const uint vh = gid % num_v_heads;
    const float x = alpha_raw[gid] + dt_bias[vh];
    const float softplus = max(x, 0.0f) + log1p(exp(-fabs(x)));
    const float log_g = softplus * ssm_a[vh];
    decay_out[gid] = exp(log_g);
    beta_out[gid] = 1.0f / (1.0f + exp(-beta_raw[gid]));
}

// One thread owns one v-head and performs a single recurrent token step.
// State layout matches RC9.2 native CUDA: [V][column][row].
kernel void rc10_gdn_step_reference(
    device const float* q          [[buffer(0)]],   // [K,D]
    device const float* k          [[buffer(1)]],   // [K,D]
    device const float* v          [[buffer(2)]],   // [V,D]
    device const float* decay      [[buffer(3)]],   // [V]
    device const float* beta       [[buffer(4)]],   // [V]
    device float* state            [[buffer(5)]],   // [V,D,D] col-major-in-head
    device float* out              [[buffer(6)]],   // [V,D]
    constant uint& num_k_heads     [[buffer(7)]],
    constant uint& num_v_heads     [[buffer(8)]],
    constant uint& head_dim        [[buffer(9)]],
    uint vh [[thread_position_in_grid]]) {
    if (vh >= num_v_heads || head_dim == 0 || head_dim > 128 || num_k_heads == 0) return;
    // Current HF Qwen3.5 repeats each key head contiguously across value heads.
    // Do not use the legacy RC9.2 modulo mapping here.
    if ((num_v_heads % num_k_heads) != 0) return;
    const uint heads_per_key = num_v_heads / num_k_heads;
    const uint kh = vh / heads_per_key;
    const uint qoff = kh * head_dim;
    const uint koff = kh * head_dim;
    const uint voff = vh * head_dim;
    const uint soff = vh * head_dim * head_dim;
    const float g = decay[vh];
    const float b = beta[vh];
    const float scale = rsqrt((float)head_dim);

    for (uint col = 0; col < head_dim; ++col) {
        float kv = 0.0f;
        for (uint row = 0; row < head_dim; ++row) {
            kv += state[soff + col * head_dim + row] * k[koff + row];
        }
        const float delta = (v[voff + col] - g * kv) * b;
        float attn = 0.0f;
        for (uint row = 0; row < head_dim; ++row) {
            const uint idx = soff + col * head_dim + row;
            const float next = g * state[idx] + k[koff + row] * delta;
            state[idx] = next;
            attn += next * q[qoff + row];
        }
        out[voff + col] = attn * scale;
    }
}

// Correctness-first fixed-input HYPIC capture. One thread owns one v-head and
// produces dense row-major T/Z for tokens [seam_width:token_count].
// The update uses the rank-1 identity:
//   T_i X = g_i (X - beta_i k_i (k_i^T X))
// so no per-token dense transition matrix is materialized.
kernel void rc10_gdn_capture_tail_reference(
    device const float* k          [[buffer(0)]],   // [T,K,D]
    device const float* v          [[buffer(1)]],   // [T,V,D]
    device const float* decay      [[buffer(2)]],   // [T,V]
    device const float* beta       [[buffer(3)]],   // [T,V]
    device float* T_out            [[buffer(4)]],   // [V,D,D] row-major
    device float* Z_out            [[buffer(5)]],   // [V,D,D] row-major
    constant uint& token_count     [[buffer(6)]],
    constant uint& num_k_heads     [[buffer(7)]],
    constant uint& num_v_heads     [[buffer(8)]],
    constant uint& head_dim        [[buffer(9)]],
    constant uint& seam_width      [[buffer(10)]],
    uint vh [[thread_position_in_grid]]) {
    if (vh >= num_v_heads || num_k_heads == 0 || head_dim == 0 || head_dim > 128) return;
    if (seam_width >= token_count || (num_v_heads % num_k_heads) != 0) return;
    const uint heads_per_key = num_v_heads / num_k_heads;
    const uint kh = vh / heads_per_key;
    const uint base = vh * head_dim * head_dim;

    for (uint r = 0; r < head_dim; ++r) {
        for (uint c = 0; c < head_dim; ++c) {
            T_out[base + r * head_dim + c] = (r == c) ? 1.0f : 0.0f;
            Z_out[base + r * head_dim + c] = 0.0f;
        }
    }

    thread float projT[128];
    thread float projZ[128];
    for (uint t = seam_width; t < token_count; ++t) {
        const uint koff = (t * num_k_heads + kh) * head_dim;
        const uint voff = (t * num_v_heads + vh) * head_dim;
        const float g = decay[t * num_v_heads + vh];
        const float b = beta[t * num_v_heads + vh];

        for (uint c = 0; c < head_dim; ++c) {
            float pT = 0.0f;
            float pZ = 0.0f;
            for (uint i = 0; i < head_dim; ++i) {
                const float ki = k[koff + i];
                pT += ki * T_out[base + i * head_dim + c];
                pZ += ki * Z_out[base + i * head_dim + c];
            }
            projT[c] = pT;
            projZ[c] = pZ;
        }

        for (uint r = 0; r < head_dim; ++r) {
            const float kr = k[koff + r];
            for (uint c = 0; c < head_dim; ++c) {
                const uint idx = base + r * head_dim + c;
                T_out[idx] = g * (T_out[idx] - b * kr * projT[c]);
                Z_out[idx] = g * (Z_out[idx] - b * kr * projZ[c]) + b * kr * v[voff + c];
            }
        }
    }
}

// Correctness-first causal depthwise convolution seam replay. One thread owns
// one channel and replays the selected seam against a newly supplied incoming
// history. Weight convention matches the bundled RC9.2 CUDA path: weights
// [0..K-2] multiply the oldest->newest history samples and weight[K-1]
// multiplies the current projected token. The output applies SiLU.
kernel void rc10_conv_seam_reference(
    device const float* projected      [[buffer(0)]], // [T,C]
    device const float* initial_state  [[buffer(1)]], // [C,K-1]
    device const float* conv_w         [[buffer(2)]], // [C,K]
    device float* out                  [[buffer(3)]], // [T,C]
    device float* final_state          [[buffer(4)]], // [C,K-1]
    constant uint& token_count         [[buffer(5)]],
    constant uint& conv_dim            [[buffer(6)]],
    constant uint& kernel_size         [[buffer(7)]],
    uint c [[thread_position_in_grid]]) {
    if (c >= conv_dim || kernel_size == 0 || kernel_size > 32) return;
    const uint history = kernel_size - 1;
    const uint woff = c * kernel_size;
    const uint soff = c * history;

    for (uint t = 0; t < token_count; ++t) {
        float acc = conv_w[woff + kernel_size - 1] * projected[t * conv_dim + c];
        for (uint k = 0; k < history; ++k) {
            const int source_t = int(t) + int(k) - int(history);
            const float x = source_t >= 0
                ? projected[uint(source_t) * conv_dim + c]
                : initial_state[soff + uint(source_t + int(history))];
            acc += conv_w[woff + k] * x;
        }
        out[t * conv_dim + c] = acc / (1.0f + exp(-acc));
    }

    for (uint k = 0; k < history; ++k) {
        const int source_t = int(token_count) - int(history) + int(k);
        final_state[soff + k] = source_t >= 0
            ? projected[uint(source_t) * conv_dim + c]
            : initial_state[soff + uint(source_t + int(history))];
    }
}
