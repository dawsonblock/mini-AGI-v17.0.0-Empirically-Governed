#include "rc10_affine_reference.hpp"
#include <cassert>
#include <cmath>
#include <iostream>

int main() {
    using namespace qw3::rc10;
    constexpr std::size_t N=2;
    std::array<double,N> k1{0.8,0.6}, v1{0.2,-0.3};
    std::array<double,N> k2{0.6,-0.8}, v2{0.4,0.1};
    auto a = gdn_token_affine<N>(k1,v1,0.95,0.4);
    auto b = gdn_token_affine<N>(k2,v2,0.90,0.3);
    Matrix<N> s{0.1,0.2,-0.3,0.4};
    auto direct = b.apply(a.apply(s));
    auto composed = a.then(b).apply(s);
    for (std::size_t i=0;i<N*N;++i) assert(std::abs(direct[i]-composed[i]) < 1e-12);
    std::cout << "rc10 affine reference: PASS\n";
}
