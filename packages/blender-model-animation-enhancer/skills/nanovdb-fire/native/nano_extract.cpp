// Native bridge; build against reviewed OpenVDB/NanoVDB v12.1.0.
#include <openvdb/openvdb.h>
#include <openvdb/io/File.h>
#include <nanovdb/tools/CreateNanoGrid.h>
#include <nanovdb/io/IO.h>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <cmath>
int main(int argc,char** argv) try {
 if(argc!=11) throw std::runtime_error("input.vdb grid output.nvdb output.f32 ox oy oz nx ny nz");
 int o[3],n[3];for(int i=0;i<3;i++){o[i]=std::stoi(argv[5+i]); n[i]=std::stoi(argv[8+i]);if(n[i]<1||n[i]>96||std::abs(double(o[i]))>1000000)throw std::runtime_error("crop limit");}
 openvdb::initialize();openvdb::io::File file(argv[1]);file.open();auto g=openvdb::gridPtrCast<openvdb::FloatGrid>(file.readGrid(argv[2]));file.close();if(!g)throw std::runtime_error("FloatGrid required");
 auto handle=nanovdb::tools::createNanoGrid(*g);if(!handle.grid<float>())throw std::runtime_error("NanoVDB float conversion failed");
 nanovdb::io::writeGrid(argv[3],handle);auto read=nanovdb::io::readGrid(argv[3]);auto grid=read.grid<float>();if(!grid)throw std::runtime_error("readback failed");
 auto na=grid->getAccessor();auto oa=g->getConstAccessor();std::ofstream out(argv[4],std::ios::binary|std::ios::trunc);if(!out)throw std::runtime_error("output open");
 for(int x=0;x<n[0];++x)for(int y=0;y<n[1];++y)for(int z=0;z<n[2];++z){int i=o[0]+x,j=o[1]+y,k=o[2]+z;float v=na.getValue(nanovdb::Coord(i,j,k));float base=oa.getValue(openvdb::Coord(i,j,k));if(!std::isfinite(v)||v!=base)throw std::runtime_error("lossless crop mismatch");out.write(reinterpret_cast<const char*>(&v),sizeof(v));}
 if(!out)throw std::runtime_error("write failed");return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
