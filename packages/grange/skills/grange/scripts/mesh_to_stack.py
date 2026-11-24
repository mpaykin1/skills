#!/usr/bin/env python3
"""Convert an authored, UV/vertex-colored mesh to RGBA XY surface slices.
CPU, trimesh + NumPy + Pillow. Conservative dense barycentric surface sampling.
Does not infer unseen geometry, invent texture, or fill cavities. Inspect thin details.
For glTF/PBR use a validated, consistently lit baked color texture as source.
"""
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
from PIL import Image
import trimesh


def color_fn(mesh):
    vis=mesh.visual
    if vis.kind=='texture':
        mat=vis.material
        if hasattr(mat,'materials'):raise ValueError('split multi-material mesh into one material per primitive')
        image=getattr(mat,'image',None)
        if image is None:image=getattr(mat,'baseColorTexture',None)
        if image is None or vis.uv is None:raise ValueError('explicit baked texture and UV required')
        img=np.array(image.convert('RGBA'));uv=np.asarray(vis.uv,float)
        if uv.shape!=(len(mesh.vertices),2) or not np.isfinite(uv).all():raise ValueError('invalid UV')
        h,w=img.shape[:2]
        def lookup(face,bary):
            xy=bary@uv[face];x=np.floor((xy[:,0]%1)*w).astype(int);y=np.minimum(h-1,np.floor((1-(xy[:,1]%1))*h).astype(int))
            return img[y,x]
        return lookup
    if vis.kind=='vertex':
        vc=np.asarray(vis.vertex_colors,float)
        return lambda face,bary:np.rint(bary@vc[face]).clip(0,255).astype('uint8')
    if vis.kind=='face':
        fc=np.asarray(vis.face_colors,np.uint8)
        return lambda face,bary:None # face-specific path below
    raise ValueError('mesh without authored color/texture; do not synthesize substitute')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mesh');p.add_argument('output');p.add_argument('--resolution',type=int,default=256);p.add_argument('--max-samples',type=int,default=30000000);a=p.parse_args()
    if not 32<=a.resolution<=512:raise ValueError('resolution 32–512')
    src=Path(a.mesh).resolve();scene=trimesh.load(src,force='scene',process=False)
    meshes=[]
    for node in scene.graph.nodes_geometry:
        tr,gn=scene.graph[node];mesh=scene.geometry[gn].copy();mesh.apply_transform(tr);meshes.append(mesh)
    if not meshes:raise ValueError('no mesh geometry')
    bounds=np.stack([m.bounds for m in meshes]);lo=bounds[:,0].min(0);hi=bounds[:,1].max(0);extent=hi-lo
    if not np.isfinite(extent).all() or extent.max()<=0:raise ValueError('invalid bounds')
    step=float(extent.max()/(a.resolution-4));center=(lo+hi)/2;dims=np.maximum(4,np.ceil(extent/step).astype(int)+4)
    nx,ny,nz=map(int,dims);v=np.zeros((nz,ny,nx,4),np.uint8);distance=np.full(v.shape[:3],np.inf,np.float32);origin=center-dims*step/2
    total=0
    for mesh in meshes:
        lookup=color_fn(mesh);vertices=np.asarray(mesh.vertices,float)
        for fi,face in enumerate(mesh.faces):
            tri=vertices[face];length=max(np.linalg.norm(tri[0]-tri[1]),np.linalg.norm(tri[1]-tri[2]),np.linalg.norm(tri[2]-tri[0]));n=max(1,math.ceil(length/(step*.36)))
            total+=(n+1)*(n+2)//2
            if total>a.max_samples:raise ValueError('sample budget exceeded: split mesh into parts or explicitly raise budget')
            # Dense triangular lattice; each row is bounded in memory.
            for i in range(n+1):
                j=np.arange(n+1-i);bary=np.stack([np.full(len(j),i/n),j/n,1-(i+j)/n],axis=1);pos=bary@tri
                colors=np.broadcast_to(np.asarray(mesh.visual.face_colors[fi],np.uint8),(len(j),4)) if mesh.visual.kind=='face' else lookup(face,bary)
                ijk=np.floor((pos-origin)/step).astype(int);valid=(colors[:,3]>=128)&((ijk>=0)&(ijk<dims)).all(1)
                ijk=ijk[valid];pos=pos[valid];colors=colors[valid]
                if not len(ijk):continue
                err=np.sum((pos-(origin+(ijk+.5)*step))**2,axis=1)
                # Resolve duplicate cells in this row by nearest sample, not arbitrary last write.
                x,y,z=ijk.T;y=ny-1-y;ids=(z*ny+y)*nx+x;order=np.argsort(err,kind='stable');_,first=np.unique(ids[order],return_index=True);k=order[first];x,y,z=x[k],y[k],z[k];err=err[k];colors=colors[k]
                keep=err<distance[z,y,x];x,y,z=x[keep],y[keep],z[keep];distance[z,y,x]=err[keep];v[z,y,x]=colors[keep]
    if not (v[...,3]>=128).any():raise ValueError('no opaque surface cells')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);(out/'layers').mkdir(exist_ok=True);paths=[]
    for i,layer in enumerate(v):
        name=f'layers/{i:04}.png';Image.fromarray(layer,'RGBA').save(out/name);paths.append(name)
    m={'layers':paths,'layer_sha256':[hashlib.sha256((out/f).read_bytes()).hexdigest() for f in paths],'spacing':[step]*3,'pivot':[0,0,0],'source_center_world':center.tolist(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_format':src.suffix,'method':'dense_uv_or_vertex_surface_sampling','samples':total,'size':320,'status':'CANDIDATE_NOT_APPROVED'}
    (out/'stack.json').write_text(json.dumps(m,indent=2));print(json.dumps({'layers':nz,'xy':[nx,ny],'samples':total,'status':m['status']}))

if __name__=='__main__':main()
