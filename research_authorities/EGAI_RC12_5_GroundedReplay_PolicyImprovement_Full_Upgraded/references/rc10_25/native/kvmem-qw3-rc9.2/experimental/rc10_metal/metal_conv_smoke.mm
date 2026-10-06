#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cmath>
#include <cstring>
#include <iostream>

static bool near(float a, float b, float tol=2e-4f) { return std::fabs(a-b) <= tol; }

int main(int argc, char** argv) {
    @autoreleasepool {
        if (argc != 2) { std::cerr << "usage: metal_conv_smoke <rc10.metallib>\n"; return 2; }
        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        if (!dev) { std::cerr << "no Metal device\n"; return 3; }
        NSError* error=nil;
        id<MTLLibrary> lib=[dev newLibraryWithFile:[NSString stringWithUTF8String:argv[1]] error:&error];
        if (!lib) { std::cerr << [[error description] UTF8String] << "\n"; return 4; }
        id<MTLFunction> fn=[lib newFunctionWithName:@"rc10_conv_seam_reference"];
        id<MTLComputePipelineState> pipe=[dev newComputePipelineStateWithFunction:fn error:&error];
        if (!pipe) { std::cerr << [[error description] UTF8String] << "\n"; return 5; }

        const uint32_t T=2,C=1,K=3;
        const float x[2]={4.0f,5.0f}, state[2]={2.0f,3.0f}, w[3]={1.0f,2.0f,3.0f};
        auto buf=[&](const void* p,size_t n){ return [dev newBufferWithBytes:p length:n options:MTLResourceStorageModeShared]; };
        id<MTLBuffer> bx=buf(x,sizeof(x)), bs=buf(state,sizeof(state)), bw=buf(w,sizeof(w));
        id<MTLBuffer> bo=[dev newBufferWithLength:sizeof(x) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bf=[dev newBufferWithLength:sizeof(state) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bT=buf(&T,sizeof(T)), bC=buf(&C,sizeof(C)), bK=buf(&K,sizeof(K));
        id<MTLCommandQueue> q=[dev newCommandQueue]; id<MTLCommandBuffer> cmd=[q commandBuffer];
        id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder]; [enc setComputePipelineState:pipe];
        [enc setBuffer:bx offset:0 atIndex:0]; [enc setBuffer:bs offset:0 atIndex:1]; [enc setBuffer:bw offset:0 atIndex:2];
        [enc setBuffer:bo offset:0 atIndex:3]; [enc setBuffer:bf offset:0 atIndex:4];
        [enc setBuffer:bT offset:0 atIndex:5]; [enc setBuffer:bC offset:0 atIndex:6]; [enc setBuffer:bK offset:0 atIndex:7];
        [enc dispatchThreads:MTLSizeMake(C,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)]; [enc endEncoding]; [cmd commit]; [cmd waitUntilCompleted];
        const float* o=(const float*)[bo contents]; const float* f=(const float*)[bf contents];
        const float a0=20.0f, a1=26.0f;
        const float e0=a0/(1.0f+std::exp(-a0)), e1=a1/(1.0f+std::exp(-a1));
        if(!near(o[0],e0)||!near(o[1],e1)||!near(f[0],4.0f)||!near(f[1],5.0f)) {
            std::cerr << "conv mismatch\n"; return 6;
        }
        std::cout << "RC10 Metal causal-conv seam smoke: PASS (" << [[dev name] UTF8String] << ")\n";
    }
    return 0;
}
