#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cmath>
#include <iostream>

int main(int argc, char** argv) {
    @autoreleasepool {
        if (argc != 2) {
            std::cerr << "usage: metal_affine_smoke <rc10_affine.metallib>\n";
            return 2;
        }
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { std::cerr << "no Metal device\n"; return 3; }
        NSError* error = nil;
        NSString* path = [NSString stringWithUTF8String:argv[1]];
        id<MTLLibrary> lib = [device newLibraryWithFile:path error:&error];
        if (!lib) { std::cerr << [[error description] UTF8String] << "\n"; return 4; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"rc10_affine_left"];
        id<MTLComputePipelineState> pipe = [device newComputePipelineStateWithFunction:fn error:&error];
        if (!pipe) { std::cerr << [[error description] UTF8String] << "\n"; return 5; }

        const uint32_t n = 2;
        const float T[4] = {0.9f, 0.0f, 0.0f, 0.8f};
        const float S[4] = {1.0f, 2.0f, 3.0f, 4.0f};
        const float Z[4] = {0.1f, 0.2f, 0.3f, 0.4f};
        id<MTLBuffer> bT = [device newBufferWithBytes:T length:sizeof(T) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bS = [device newBufferWithBytes:S length:sizeof(S) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bZ = [device newBufferWithBytes:Z length:sizeof(Z) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bO = [device newBufferWithLength:sizeof(S) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bN = [device newBufferWithBytes:&n length:sizeof(n) options:MTLResourceStorageModeShared];
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLCommandBuffer> cmd = [queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:pipe];
        [enc setBuffer:bT offset:0 atIndex:0];
        [enc setBuffer:bS offset:0 atIndex:1];
        [enc setBuffer:bZ offset:0 atIndex:2];
        [enc setBuffer:bO offset:0 atIndex:3];
        [enc setBuffer:bN offset:0 atIndex:4];
        MTLSize grid = MTLSizeMake(n, n, 1);
        MTLSize group = MTLSizeMake(n, n, 1);
        [enc dispatchThreads:grid threadsPerThreadgroup:group];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];

        const float* O = static_cast<const float*>([bO contents]);
        const float expected[4] = {1.0f, 2.0f, 2.7f, 3.6f};
        for (int i=0;i<4;++i) {
            if (std::fabs(O[i]-expected[i]) > 1e-5f) {
                std::cerr << "mismatch at " << i << ": " << O[i] << " vs " << expected[i] << "\n";
                return 6;
            }
        }
        std::cout << "RC10 Metal affine smoke: PASS (" << [[device name] UTF8String] << ")\n";
    }
    return 0;
}
