#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cmath>
#include <cstring>
#include <iostream>
#include <vector>

static bool near(float a, float b, float tol=3e-4f) { return std::fabs(a-b) <= tol; }

static id<MTLComputePipelineState> pipeline(id<MTLDevice> dev, id<MTLLibrary> lib, NSString* name) {
    NSError* error=nil;
    id<MTLFunction> fn=[lib newFunctionWithName:name];
    if (!fn) { std::cerr << "missing Metal function: " << [name UTF8String] << "\n"; return nil; }
    id<MTLComputePipelineState> p=[dev newComputePipelineStateWithFunction:fn error:&error];
    if (!p && error) std::cerr << [[error description] UTF8String] << "\n";
    return p;
}

int main(int argc, char** argv) {
    @autoreleasepool {
        if (argc != 2) { std::cerr << "usage: metal_gdn_smoke <rc10.metallib>\n"; return 2; }
        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        if (!dev) { std::cerr << "no Metal device\n"; return 3; }
        NSError* error=nil;
        NSString* path=[NSString stringWithUTF8String:argv[1]];
        id<MTLLibrary> lib=[dev newLibraryWithFile:path error:&error];
        if (!lib) { std::cerr << [[error description] UTF8String] << "\n"; return 4; }
        id<MTLComputePipelineState> cap=pipeline(dev,lib,@"rc10_gdn_capture_tail_reference");
        if (!cap) return 5;

        // Multi-head case intentionally detects the Qwen repeat_interleave mapping:
        // K=2, V=4 => value heads [0,1] use k0 and [2,3] use k1.
        const uint32_t Tn=4,K=2,V=4,D=2,seam=1;
        std::vector<float> k(Tn*K*D), v(Tn*V*D), g(Tn*V), b(Tn*V);
        for (uint32_t t=0;t<Tn;++t) {
            for (uint32_t kh=0;kh<K;++kh) {
                const float x=0.15f+0.09f*float(t)+0.17f*float(kh);
                k[(t*K+kh)*D+0]=std::cos(x);
                k[(t*K+kh)*D+1]=std::sin(x);
            }
            for (uint32_t vh=0;vh<V;++vh) {
                v[(t*V+vh)*D+0]=0.04f*float(1+t+vh);
                v[(t*V+vh)*D+1]=-0.03f*float(1+2*t+vh);
                g[t*V+vh]=0.82f+0.02f*float((t+vh)%4);
                b[t*V+vh]=0.20f+0.05f*float(vh);
            }
        }
        std::vector<float> Tgpu(V*D*D,0.0f), Zgpu(V*D*D,0.0f);

        auto buf=[&](const void* p, size_t n){ return [dev newBufferWithBytes:p length:n options:MTLResourceStorageModeShared]; };
        id<MTLBuffer> bk=buf(k.data(),k.size()*sizeof(float)), bv=buf(v.data(),v.size()*sizeof(float));
        id<MTLBuffer> bg=buf(g.data(),g.size()*sizeof(float)), bb=buf(b.data(),b.size()*sizeof(float));
        id<MTLBuffer> bT=[dev newBufferWithLength:Tgpu.size()*sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bZ=[dev newBufferWithLength:Zgpu.size()*sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bTn=buf(&Tn,sizeof(Tn)), bK=buf(&K,sizeof(K)), bV=buf(&V,sizeof(V)), bD=buf(&D,sizeof(D)), bSeam=buf(&seam,sizeof(seam));
        id<MTLCommandQueue> q=[dev newCommandQueue];
        id<MTLCommandBuffer> cmd=[q commandBuffer];
        id<MTLComputeCommandEncoder> enc=[cmd computeCommandEncoder];
        [enc setComputePipelineState:cap];
        [enc setBuffer:bk offset:0 atIndex:0]; [enc setBuffer:bv offset:0 atIndex:1];
        [enc setBuffer:bg offset:0 atIndex:2]; [enc setBuffer:bb offset:0 atIndex:3];
        [enc setBuffer:bT offset:0 atIndex:4]; [enc setBuffer:bZ offset:0 atIndex:5];
        [enc setBuffer:bTn offset:0 atIndex:6]; [enc setBuffer:bK offset:0 atIndex:7];
        [enc setBuffer:bV offset:0 atIndex:8]; [enc setBuffer:bD offset:0 atIndex:9];
        [enc setBuffer:bSeam offset:0 atIndex:10];
        [enc dispatchThreads:MTLSizeMake(V,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [enc endEncoding]; [cmd commit]; [cmd waitUntilCompleted];
        std::memcpy(Tgpu.data(),[bT contents],Tgpu.size()*sizeof(float));
        std::memcpy(Zgpu.data(),[bZ contents],Zgpu.size()*sizeof(float));

        std::vector<float> Tcpu(V*D*D,0.0f), Zcpu(V*D*D,0.0f);
        const uint32_t headsPerKey=V/K;
        for (uint32_t vh=0;vh<V;++vh) {
            const uint32_t kh=vh/headsPerKey;
            float* Tc=Tcpu.data()+vh*D*D; float* Zc=Zcpu.data()+vh*D*D;
            Tc[0]=1.0f; Tc[3]=1.0f;
            for (uint32_t t=seam;t<Tn;++t) {
                float pT[2]={0,0},pZ[2]={0,0};
                const float* kt=k.data()+(t*K+kh)*D;
                const float* vt=v.data()+(t*V+vh)*D;
                for(uint32_t c=0;c<D;++c) for(uint32_t i=0;i<D;++i){
                    pT[c]+=kt[i]*Tc[i*D+c]; pZ[c]+=kt[i]*Zc[i*D+c];
                }
                float nt[4],nz[4];
                for(uint32_t r=0;r<D;++r) for(uint32_t c=0;c<D;++c){
                    const uint32_t idx=r*D+c;
                    nt[idx]=g[t*V+vh]*(Tc[idx]-b[t*V+vh]*kt[r]*pT[c]);
                    nz[idx]=g[t*V+vh]*(Zc[idx]-b[t*V+vh]*kt[r]*pZ[c])+b[t*V+vh]*kt[r]*vt[c];
                }
                std::memcpy(Tc,nt,sizeof(nt)); std::memcpy(Zc,nz,sizeof(nz));
            }
        }
        for(size_t i=0;i<Tgpu.size();++i) {
            if(!near(Tgpu[i],Tcpu[i]) || !near(Zgpu[i],Zcpu[i])) {
                std::cerr << "capture mismatch at " << i << " T=" << Tgpu[i] << "/" << Tcpu[i]
                          << " Z=" << Zgpu[i] << "/" << Zcpu[i] << "\n"; return 6;
            }
        }
        std::cout << "RC10 Metal Qwen3.5 GDN/HYPIC grouped-head smoke: PASS (" << [[dev name] UTF8String] << ")\n";
    }
    return 0;
}
