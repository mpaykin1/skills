// CPU-only bridge to Pixar OpenSubdiv Far, triangular Loop subdivision.
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>
#include <opensubdiv/far/primvarRefiner.h>
#include <opensubdiv/sdc/options.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <memory>
#include <iomanip>
#include <stdexcept>
#include <cmath>
using namespace OpenSubdiv;
struct Point {
    float xyz[3] = {0,0,0};
    void Clear(void* = nullptr) { for (auto &x : xyz) x=0; }
    void AddWithWeight(Point const &p, float w) { for (int j=0;j<3;++j) xyz[j]+=p.xyz[j]*w; }
};
int main(int argc,char** argv) {
 try {
    if(argc!=3) throw std::runtime_error("input and output paths required");
    std::ifstream in(argv[1]); int nv=0,nf=0,nc=0,level=0;
    if(!(in>>nv>>nf>>nc>>level)||nv<3||nv>200000||nf<1||nf>200000||nc<0||nc>3*nf||level<1||level>2||nf*(1<<(2*level))>1000000) throw std::runtime_error("invalid mesh budget");
    std::vector<Point> points(nv); std::vector<int> counts(nf,3), faces(3*nf), edges(2*nc); std::vector<float> sharpness(nc);
    for(auto &p:points) for(float &x:p.xyz) if(!(in>>x)||!std::isfinite(x)) throw std::runtime_error("invalid point");
    for(auto &i:faces) if(!(in>>i)||i<0||i>=nv) throw std::runtime_error("invalid index");
    for(int i=0;i<nc;++i) { if(!(in>>edges[2*i]>>edges[2*i+1]>>sharpness[i])||edges[2*i]<0||edges[2*i]>=nv||edges[2*i+1]<0||edges[2*i+1]>=nv||sharpness[i]!=10.f) throw std::runtime_error("invalid crease"); }
    Far::TopologyDescriptor desc; desc.numVertices=nv; desc.numFaces=nf; desc.numVertsPerFace=counts.data(); desc.vertIndicesPerFace=faces.data();
    desc.numCreases=nc; desc.creaseVertexIndexPairs=edges.data(); desc.creaseWeights=sharpness.data();
    Sdc::Options scheme; scheme.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_AND_CORNER);
    using Factory=Far::TopologyRefinerFactory<Far::TopologyDescriptor>;
    std::unique_ptr<Far::TopologyRefiner> ref(Factory::Create(desc,Factory::Options(Sdc::SCHEME_LOOP,scheme)));
    if(!ref) throw std::runtime_error("OpenSubdiv topology failed");
    Far::TopologyRefiner::UniformOptions opts(level); opts.fullTopologyInLastLevel=true; ref->RefineUniform(opts);
    Far::PrimvarRefiner primvars(*ref);
    for(int i=1;i<=level;++i) {
        std::vector<Point> next(ref->GetLevel(i).GetNumVertices());
        auto const* src=points.data(); auto* dst=next.data();
        primvars.Interpolate(i,src,dst); points.swap(next);
    }
    auto const& top=ref->GetLevel(level);
    std::ofstream out(argv[2]); out<<std::setprecision(9)<<points.size()<<' '<<top.GetNumFaces()<<'\n';
    for(auto const& p:points) out<<p.xyz[0]<<' '<<p.xyz[1]<<' '<<p.xyz[2]<<'\n';
    for(int f=0;f<top.GetNumFaces();++f) { auto indices=top.GetFaceVertices(f); if(indices.size()!=3) throw std::runtime_error("nontriangle output"); out<<indices[0]<<' '<<indices[1]<<' '<<indices[2]<<'\n'; }
    if(!out) throw std::runtime_error("output write failed"); return 0;
 } catch(std::exception const& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
