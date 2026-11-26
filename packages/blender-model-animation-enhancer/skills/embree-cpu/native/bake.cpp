// Original CPU-only Embree adapter. Not a path tracer or gameplay collider.
#include <embree4/rtcore.h>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <stdexcept>
#include <algorithm>
struct V{float x,y,z; V operator+(V b)const{return{x+b.x,y+b.y,z+b.z};} V operator-(V b)const{return{x-b.x,y-b.y,z-b.z};} V operator*(float k)const{return{x*k,y*k,z*k};}};
struct T{uint32_t a,b,c;};
float dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
V cross(V a,V b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
V norm(V a){float l=std::sqrt(dot(a,a));if(!(l>1e-8f)||!std::isfinite(l))throw std::runtime_error("invalid normal");return a*(1/l);}
V readv(){V v;if(!(std::cin>>v.x>>v.y>>v.z)||!std::isfinite(v.x)||!std::isfinite(v.y)||!std::isfinite(v.z))throw std::runtime_error("invalid vector");return v;}
bool blocked(RTCScene s,V o,V d,float far){RTCRay r{};r.org_x=o.x;r.org_y=o.y;r.org_z=o.z;r.dir_x=d.x;r.dir_y=d.y;r.dir_z=d.z;r.tnear=0;r.tfar=far;r.mask=0xffffffffu;r.time=0;RTCOccludedArguments a;rtcInitOccludedArguments(&a);rtcOccluded1(s,&r,&a);return r.tfar<0;}
int main(){RTCDevice dev=nullptr;RTCScene scene=nullptr;RTCGeometry geom=nullptr;try{
 uint32_t nv,nt,np,ns,threads;float radius,eps; if(!(std::cin>>nv>>nt>>np>>ns>>threads>>radius>>eps)||nv<3||nv>2000000||nt<1||nt>2000000||np<1||np>262144||ns<8||ns>128||threads<1||threads>32||!(radius>eps&&eps>0&&radius<=1000))throw std::runtime_error("invalid dimensions");
 auto light=readv();std::string cfg="threads="+std::to_string(threads);dev=rtcNewDevice(cfg.c_str());if(!dev)throw std::runtime_error("Embree device unavailable");scene=rtcNewScene(dev);geom=rtcNewGeometry(dev,RTC_GEOMETRY_TYPE_TRIANGLE);if(!scene||!geom)throw std::runtime_error("scene allocation failed");
 rtcSetSceneFlags(scene,RTC_SCENE_FLAG_ROBUST);auto *v=static_cast<V*>(rtcSetNewGeometryBuffer(geom,RTC_BUFFER_TYPE_VERTEX,0,RTC_FORMAT_FLOAT3,sizeof(V),nv));auto *t=static_cast<T*>(rtcSetNewGeometryBuffer(geom,RTC_BUFFER_TYPE_INDEX,0,RTC_FORMAT_UINT3,sizeof(T),nt));if(!v||!t)throw std::runtime_error("geometry allocation failed");for(uint32_t i=0;i<nv;i++)v[i]=readv();for(uint32_t i=0;i<nt;i++){if(!(std::cin>>t[i].a>>t[i].b>>t[i].c)||std::max({t[i].a,t[i].b,t[i].c})>=nv)throw std::runtime_error("invalid triangle");}rtcCommitGeometry(geom);rtcAttachGeometry(scene,geom);rtcReleaseGeometry(geom);geom=nullptr;rtcCommitScene(scene);if(rtcGetDeviceError(dev)!=RTC_ERROR_NONE)throw std::runtime_error("scene build failed");
 std::cout<<std::setprecision(9);for(uint32_t i=0;i<np;i++){V p=readv(),n=norm(readv());V o=p+n*eps;V a=norm(cross(std::abs(n.z)<.9f?V{0,0,1}:V{0,1,0},n)),b=cross(n,a);unsigned hits=0;for(uint32_t j=0;j<ns;j++){float u=(j+.5f)/ns,phi=6.28318530718f*std::fmod(j*.61803398875f,1.f);V dir=norm(a*(std::sqrt(u)*std::cos(phi))+b*(std::sqrt(u)*std::sin(phi))+n*std::sqrt(1-u));hits+=blocked(scene,o,dir,radius);}V delta=light-o;float dist=std::sqrt(dot(delta,delta));bool vis=dist>2*eps&&dot(n,delta)>0&&!blocked(scene,o,delta*(1/dist),dist-eps);std::cout<<1.f-float(hits)/ns<<' '<<int(vis)<<'\n';}if(rtcGetDeviceError(dev)!=RTC_ERROR_NONE)throw std::runtime_error("ray query failed");rtcReleaseScene(scene);rtcReleaseDevice(dev);return 0;
 }catch(const std::exception&e){if(geom)rtcReleaseGeometry(geom);if(scene)rtcReleaseScene(scene);if(dev)rtcReleaseDevice(dev);std::cerr<<e.what()<<'\n';return 1;}}
