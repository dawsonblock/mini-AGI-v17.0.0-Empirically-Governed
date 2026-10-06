#pragma once
#include <array>
#include <cstddef>
#include <stdexcept>

namespace qw3::rc10 {

enum class TransitionOrientation { LeftMultiply, RightMultiply };

template <std::size_t N>
using Matrix = std::array<double, N * N>;

template <std::size_t N>
inline Matrix<N> matmul(const Matrix<N>& a, const Matrix<N>& b) {
    Matrix<N> out{};
    for (std::size_t i = 0; i < N; ++i)
        for (std::size_t j = 0; j < N; ++j)
            for (std::size_t k = 0; k < N; ++k)
                out[i*N+j] += a[i*N+k] * b[k*N+j];
    return out;
}

template <std::size_t N>
inline Matrix<N> add(const Matrix<N>& a, const Matrix<N>& b) {
    Matrix<N> out{};
    for (std::size_t i = 0; i < N*N; ++i) out[i] = a[i] + b[i];
    return out;
}

template <std::size_t N>
struct AffineSummary {
    Matrix<N> T{};
    Matrix<N> Z{};
    TransitionOrientation orientation{TransitionOrientation::LeftMultiply};

    Matrix<N> apply(const Matrix<N>& state) const {
        if (orientation == TransitionOrientation::LeftMultiply)
            return add<N>(matmul<N>(T, state), Z);
        return add<N>(matmul<N>(state, T), Z);
    }

    AffineSummary then(const AffineSummary& next) const {
        if (orientation != next.orientation) throw std::invalid_argument("orientation mismatch");
        AffineSummary out{};
        out.orientation = orientation;
        if (orientation == TransitionOrientation::LeftMultiply) {
            out.T = matmul<N>(next.T, T);
            out.Z = add<N>(matmul<N>(next.T, Z), next.Z);
        } else {
            out.T = matmul<N>(T, next.T);
            out.Z = add<N>(matmul<N>(Z, next.T), next.Z);
        }
        return out;
    }
};

// RC9.2 gated_delta_net.cu column-state recurrence reference:
// S' = g(I - beta*k*k^T)S + beta*k*v^T
// This assumes d_k == d_v == N for the reference test.
template <std::size_t N>
inline AffineSummary<N> gdn_token_affine(const std::array<double,N>& k,
                                         const std::array<double,N>& v,
                                         double g,
                                         double beta) {
    AffineSummary<N> out{};
    out.orientation = TransitionOrientation::LeftMultiply;
    for (std::size_t i=0;i<N;++i) {
        for (std::size_t j=0;j<N;++j) {
            const double eye = i == j ? 1.0 : 0.0;
            out.T[i*N+j] = g * (eye - beta*k[i]*k[j]);
            out.Z[i*N+j] = beta*k[i]*v[j];
        }
    }
    return out;
}

} // namespace qw3::rc10
