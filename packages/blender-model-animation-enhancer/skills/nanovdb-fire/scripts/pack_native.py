"""Extract real scalar grids with OpenVDB's Python binding; never invent a cache."""
import argparse, hashlib, json, math, sys, subprocess, tempfile, os
from pathlib import Path
import numpy as np
from PIL import Image

PIN='e4621ae7b37d993ffb93f11ded327736b8227f5f'
def digest(b): return hashlib.sha256(b).hexdigest()
def check(c,msg):
    if not c: raise ValueError(msg)
def render_projection(rgba):
    # Input z,y,x,RGBA with straight RGB and per-voxel opacity. Front = +Z.
    h,w=rgba.shape[1:3]; col=np.zeros((h,w,3),np.float32); alpha=np.zeros((h,w,1),np.float32)
    for layer in rgba[::-1]:
        l=layer.astype(np.float32)/255; a=l[...,3:4]*(1-alpha)
        col+=l[...,:3]*a; alpha+=a
    straight=np.divide(col,alpha,out=np.zeros_like(col),where=alpha>1e-6)
    return np.uint8(np.clip(np.concatenate([straight,alpha],-1)[::-1],0,1)*255+.5)
def volume(d,f,step,extinction,emission):
    # vdb x,y,z -> Three x,z,-y. Art-directed color, not a physical blackbody solver.
    d=np.maximum(d,0); f=np.maximum(f,0); w=1-np.exp(-f*emission)
    smoke=np.array([.16,.14,.13],np.float32); hot=np.stack([np.ones_like(w),.20+.7*w,.025+.37*w],-1)
    rgb=smoke*(1-w[...,None])+hot*w[...,None]
    a=1-np.exp(-(d*extinction+f*emission)*step)
    rgba=np.uint8(np.clip(np.concatenate([rgb,a[...,None]],-1),0,1)*255+.5)
    return np.ascontiguousarray(rgba.transpose(1,2,0,3)[::-1])
def transform(grid,origin):
    t=grid.transform; p=np.asarray(t.indexToWorld(tuple(origin)),float)
    basis=np.stack([np.asarray(t.indexToWorld(tuple(map(int,np.asarray(origin)+np.eye(3,dtype=int)[i]))),float)-p for i in range(3)],axis=1)
    check(np.isfinite(basis).all() and np.isfinite(p).all() and np.allclose(basis,np.eye(3)*basis[0,0],rtol=1e-5,atol=1e-8) and basis[0,0]>0,'axis-aligned isotropic positive grids only; resample upstream')
    check(bool(t.isLinear),'nonlinear VDB transform unsupported'); return p,basis

def main():
    ap=argparse.ArgumentParser();ap.add_argument('config',type=Path);ap.add_argument('out',type=Path);ap.add_argument('--extractor',required=True,type=Path);a=ap.parse_args(); c=json.loads(a.config.read_text()); root=a.config.resolve().parent
    import openvdb as vdb
    origin=tuple(c['origin']); shape=tuple(c['shape']); stride=c.get('stride',1); frames=c['frames']; fps=c['fps']; dname=c['density_grid']; fname=c['flame_grid']; ext=float(c.get('extinction',2)); em=float(c.get('emission',5))
    check(len(origin)==3 and all(type(x) is int for x in origin),'origin');check(len(shape)==3 and all(type(x) is int and 8<=x<=96 for x in shape),'shape 8..96');check(type(stride) is int and 1<=stride<=4 and all(x%stride==0 for x in shape),'stride must divide dimensions');check(16<=len(frames)<=64 and fps==24,'16..64 frames at 24fps');check(0<ext<=20 and 0<em<=30,'bounded shading')
    dims=tuple(x//stride for x in shape);check(max(dims)<=64 and math.prod(dims)*4*len(frames)<=32*1024*1024,'32 MiB raw volume budget');check(len({x['frame'] for x in frames})==len(frames) and all(b['frame']==a['frame']+1 for a,b in zip(frames,frames[1:])),'consecutive source frames required');check(c['source']=='blender-mantaflow','source must be actual approved Mantaflow cache')
    def load(entry):
        p=(root/entry['file']).resolve();check(p.is_relative_to(root) and p.suffix.lower()=='.vdb' and p.stat().st_size<=256*1024*1024,'cache path/size');check(digest(p.read_bytes())==entry['sha256'],'cache SHA mismatch');return p
    allpaths=[load(x) for x in frames];check(len(set(allpaths))==len(frames),'duplicate input file')
    raw=[]; images=[]; lights=[]; gridref=None
    for e,p in zip(frames,allpaths):
        grids=[vdb.read(str(p),n) for n in (dname,fname)]; arrays=[]
        for g in grids:
            pos,b=transform(g,origin)
            if gridref is None:gridref=(pos,b)
            check(np.allclose(pos,gridref[0],atol=1e-6) and np.allclose(b,gridref[1],atol=1e-8),'frame/channel transform drift')
            with tempfile.TemporaryDirectory(prefix='meta-nanovdb-') as tmp:
                nv=Path(tmp)/'grid.nvdb'; f32=Path(tmp)/'crop.f32'
                subprocess.run([str(a.extractor.resolve()),str(p),(dname,fname)[len(arrays)],str(nv),str(f32),*map(str,origin),*map(str,shape)],check=True,timeout=90)
                check(nv.is_file() and nv.stat().st_size<=256*1024*1024 and f32.stat().st_size==math.prod(shape)*4,'native output size')
                arr=np.fromfile(f32,dtype=np.float32).reshape(shape)
            check(np.isfinite(arr).all() and arr.min()>=-1e-5,'bad scalar grid')
            # Reject crop cutting visible data at domain sides/top. Base may contain fuel.
            edge=max(float(arr[0].max()),float(arr[-1].max()),float(arr[:,0].max()),float(arr[:,-1].max()),float(arr[:,:,-1].max()));check(edge<=max(.01,float(arr.max())*.04),'active volume touches crop edge; enlarge fixed bounds')
            arr=arr.reshape(dims[0],stride,dims[1],stride,dims[2],stride).mean((1,3,5));arrays.append(arr)
        d,f=arrays;check(float(f.max())>.001,'empty flame'); step=float(gridref[1][0,0])*stride; r=volume(d,f,step,ext,em);raw.append(r);images.append(render_projection(r));lights.append(float(np.clip(f.mean()*8,0,2)))
    change=[float(np.abs(x.astype(np.int16)-y.astype(np.int16)).mean()/255) for x,y in zip(raw,raw[1:])]; median=float(np.median(change));check(median>0.0001 and sum(x>0.00005 for x in change)>=.8*len(change),'static/repeated volume');seam=float(np.abs(raw[0].astype(np.int16)-raw[-1].astype(np.int16)).mean()/255);check(seam<=max(.01,4*median),'visible loop seam: choose longer bake')
    # Preserve aspect ratio by sizing to world dimensions in runtime, not by distorting camera.
    w,h=dims[0],dims[2];cols=min(2048//w,len(raw));rows=math.ceil(len(raw)/cols);check(rows*h<=2048,'fallback atlas too large')
    atlas=Image.new('RGBA',(cols*w,rows*h));
    for i,img in enumerate(images): atlas.paste(Image.fromarray(img),((i%cols)*w,(i//cols)*h))
    projection=[float(np.abs(x.astype(np.int16)-y.astype(np.int16)).mean()/255) for x,y in zip(images,images[1:])];check(np.median(projection)>.0001,'static projected fallback')
    out=a.out;out.mkdir(parents=True,exist_ok=False);data=b''.join(r.tobytes() for r in raw);(out/'volume.rgba').write_bytes(data);atlas.save(out/'fallback.png');
    sz=(dims[0],dims[2],dims[1]);m={'schema':'openvdb-fire-v1','source':'blender-mantaflow-openvdb','upstream_commit':PIN,'native_extraction':'nanovdb-float-verified-crop','fps':fps,'frames':len(raw),'size':list(sz),'world_size_m':[v*step for v in sz],'source_origin_blender_m':gridref[0].tolist(),'source_frame_sha256':[e['sha256'] for e in frames],'sha256':digest(data),'atlas_sha256':digest((out/'fallback.png').read_bytes()),'atlas_size':list(atlas.size),'cols':cols,'rows':rows,'light':lights,'volume_motion':median,'loop_seam':seam,'fallback_motion':float(np.median(projection))};(out/'volume.json').write_text(json.dumps(m,indent=2))
if __name__=='__main__':main()
