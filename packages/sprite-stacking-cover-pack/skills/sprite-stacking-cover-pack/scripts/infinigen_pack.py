"""Import individually baked Infinigen meshes into the shared Sprite Stacking grid contract.
The generator is external; no procedural geometry is fabricated by this adapter.
"""
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np
import trimesh
from trellis_stack import export_stack

ID=re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
def digest(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d): Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def newdir(p):
    p=Path(p).resolve();p.mkdir(parents=True,exist_ok=False);return p

def colors(mesh,fi,bary):
    vis=mesh.visual
    if vis.kind=='texture':
        uv=np.asarray(vis.uv,dtype=float)
        if uv.shape!=(len(mesh.vertices),2) or not np.isfinite(uv).all(): raise ValueError('Missing baked UV')
        mat=vis.material
        if isinstance(mat,trimesh.visual.material.MultiMaterial): raise ValueError('Split multiple materials upstream')
        q=np.einsum('ni,nij->nj',bary,uv[mesh.faces[fi]])
        c=mat.to_color(q)
        if c is None:
            c=getattr(mat,'diffuse',None)
        if c is None: raise ValueError('No baked texture or explicit material color')
        c=np.asarray(c,dtype=float)
        if c.ndim==1:c=np.broadcast_to(c,(len(fi),len(c))).copy()
        if c.shape!=(len(fi),4): raise ValueError('Expected RGBA material')
        # glTF baseColorFactor is linear RGB; texture RGB is sRGB.
        if getattr(mat,'baseColorTexture',None) is not None and getattr(mat,'baseColorFactor',None) is not None:
            factor=np.asarray(mat.baseColorFactor,dtype=float)/255
            s=c[:,:3]/255;lin=np.where(s<=.04045,s/12.92,((s+.055)/1.055)**2.4)*factor[:3]
            c[:,:3]=255*np.where(lin<=.0031308,lin*12.92,1.055*np.maximum(lin,0)**(1/2.4)-.055);c[:,3]*=factor[3]
        if getattr(mat,'alphaMode',None)=='MASK':
            cutoff=getattr(mat,'alphaCutoff',None);c[:,3]=np.where(c[:,3]/255 >= (.5 if cutoff is None else cutoff),255,0)
    elif vis.kind=='vertex': c=np.einsum('ni,nij->nj',bary,np.asarray(vis.vertex_colors)[mesh.faces[fi]])
    elif vis.kind=='face': c=np.asarray(vis.face_colors)[fi]
    else: raise ValueError('Missing authored material; bake it with Infinigen exporter first')
    return np.clip(c/255,0,1)

def convert(src,out,size,up,max_samples):
    scene=trimesh.load_scene(src,allow_remote=False,process=False)
    meshes=[]
    for node in sorted(scene.graph.nodes_geometry):
        transform,key=scene.graph[node];m=scene.geometry[key].copy();m.apply_transform(transform)
        if not isinstance(m,trimesh.Trimesh) or not len(m.faces) or not np.isfinite(m.vertices).all(): raise ValueError('Invalid mesh')
        meshes.append(m)
    if not meshes: raise ValueError('Empty exported object')
    lo=np.min([m.bounds[0] for m in meshes],axis=0);hi=np.max([m.bounds[1] for m in meshes],axis=0)
    extent=float(max(hi-lo));step=extent/(size-2)
    if not np.isfinite(step) or step<=0: raise ValueError('Invalid dimensions')
    origin=lo-step*.5
    samples=[];rgba=[];count=0;vertices=[];faces=[];off=0
    for m in meshes:
        tri=m.triangles;edge=np.linalg.norm(tri-np.roll(tri,1,axis=1),axis=2).max(axis=1)
        n=np.maximum(1,np.ceil(edge/(step*.45)).astype(int));count+=int(np.sum((n+1)*(n+2)//2))
        if count>max_samples: raise ValueError('Surface sample budget exceeded; use smaller size or split exported asset')
        for k in np.unique(n):
            pairs=np.array([(a,b) for a in range(k+1) for b in range(k+1-a)],dtype=float)/k
            bary=np.column_stack((1-pairs.sum(1),pairs));ids=np.flatnonzero(n==k)
            batch=max(1,65536//len(bary))
            for start in range(0,len(ids),batch):
                fi=np.repeat(ids[start:start+batch],len(bary));b=np.tile(bary,(len(ids[start:start+batch]),1))
                p=np.einsum('ni,nij->nj',b,tri[fi]);samples.append(np.floor((p-origin)/step).astype(np.int32));rgba.append(colors(m,fi,b).astype(np.float32))
        vertices.append(np.asarray(m.vertices));faces.append(np.asarray(m.faces)+off);off+=len(m.vertices)
    coords=np.concatenate(samples);rgba=np.concatenate(rgba)
    # Average only actual surface samples. Keep maximum alpha for a cell, as native export does.
    coords,inv=np.unique(coords,axis=0,return_inverse=True);weight=np.bincount(inv,weights=rgba[:,3]);a=np.zeros(len(coords),np.float32);np.maximum.at(a,inv,rgba[:,3]);rgb=np.column_stack([np.bincount(inv,weights=rgba[:,c]*rgba[:,3])/np.maximum(weight,1e-12) for c in range(3)]);rgba=np.column_stack((rgb,a)).astype(np.float32)
    out=newdir(out)
    np.savez_compressed(out/'native_grid.npz',coords=coords,rgba=rgba,voxel_size=step,origin=origin,layout=np.array('{"base_color":[0,3],"alpha":[3,4]}'),attrs=rgba)
    np.savez_compressed(out/'native_mesh.npz',vertices=np.concatenate(vertices),faces=np.concatenate(faces))
    export_stack(coords,rgba,step,out,size,up,origin)
    for file in ('stack.json','asset.json'):
        meta=read(out/file);meta.update(representation='sampled textured mesh surface; not TRELLIS inference or solid',sourceKind='infinigen-baked-mesh');write(out/file,meta)
    write(out/'geometry-source.json',{n:digest(out/n) for n in ('native_grid.npz','native_mesh.npz')})
    return {'sourceSHA256':digest(src),'samples':count,'occupiedCells':len(coords),'sourceKind':'infinigen-baked-mesh','trimeshVersion':trimesh.__version__}

def pack(args):
    root=Path(args.exported).resolve();spec=read(args.selection);out=Path(args.out).resolve()
    if not isinstance(spec,list) or not spec: raise ValueError('Select independent reviewed exported objects')
    ids=[o['id'] for o in spec]
    if len(set(ids))!=len(ids) or not all(ID.fullmatch(i) for i in ids): raise ValueError('Invalid IDs')
    if root==out or root in out.parents or out in root.parents: raise ValueError('Keep export source and output separate')
    files=[]
    for o in spec:
        f=(root/o['file']).resolve()
        if root not in f.parents or not f.is_file() or f.suffix.lower() not in ('.obj','.glb','.gltf','.ply'): raise ValueError('Invalid exported mesh path')
        files.append(f)
    # Retain complete baked export including MTL, texture maps, and source material provenance.
    if any(p.is_symlink() for p in root.rglob('*')): raise ValueError('Source export must be self-contained, without symlinks')
    out=newdir(out);shutil.copytree(root,out/'baked-source')
    records=[]
    for o,f in zip(spec,files):
        rec=convert(out/'baked-source'/f.relative_to(root),out/o['id'],args.size,args.up,args.max_samples)
        rec.update(id=o['id'],file=str(f.relative_to(root)),role=o.get('role','environment'));write(out/o['id']/'provenance.json',rec);records.append(rec)
    write(out/'generation.json',{'assets':ids,'sourceKind':'infinigen-baked-export','sourceFiles':{str(p.relative_to(out/'baked-source')):digest(p) for p in (out/'baked-source').rglob('*') if p.is_file()},'records':records,'status':'prototype; visual fidelity and animation unverified'})

def merge(args):
    roots=[Path(p).resolve() for p in args.generated];out=Path(args.out).resolve();records=[];ids=[]
    for r in roots:
        if r==out or r in out.parents or out in r.parents:raise ValueError('Separate output required')
        g=read(r/'generation.json')
        for i in g['assets']:
            if not ID.fullmatch(i) or i in ids:raise ValueError('Duplicate or invalid asset ID: '+i)
            if not (r/i/'stack.json').is_file():raise ValueError('Missing stack: '+i)
            ids.append(i)
        records.append({'root':str(r),'generationSHA256':digest(r/'generation.json'),'assets':g['assets']})
    out=newdir(out)
    for r,record in zip(roots,records):
        for i in record['assets']:shutil.copytree(r/i,out/i)
        # Source archive is preserved alongside its origin manifest, not confused with native grids.
        dest=out/'source-manifests'/str(roots.index(r));dest.mkdir(parents=True);shutil.copy2(r/'generation.json',dest/'generation.json')
        if (r/'baked-source').is_dir():shutil.copytree(r/'baked-source',dest/'baked-source')
    write(out/'generation.json',{'assets':ids,'sources':records,'status':'prototype; mixed native mesh sources'})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    e=s.add_parser('export');e.add_argument('--input-folder',required=True);e.add_argument('--out',required=True);e.add_argument('--python',default=sys.executable);e.add_argument('--texture-size',type=int,default=1024)
    c=s.add_parser('pack');c.add_argument('--exported',required=True);c.add_argument('--selection',required=True);c.add_argument('--out',required=True);c.add_argument('--up',choices=['y','z'],required=True);c.add_argument('--size',type=int,choices=[128,256,512,1024],default=256);c.add_argument('--max-samples',type=int,default=4000000)
    m=s.add_parser('merge');m.add_argument('--generated',nargs='+',required=True);m.add_argument('--out',required=True)
    a=p.parse_args()
    if a.mode=='export':
        if Path(a.out).exists():raise FileExistsError(a.out)
        subprocess.run([a.python,'-m','infinigen.tools.export','--input_folder',a.input_folder,'--output_folder',a.out,'-f','obj','-r',str(a.texture_size),'--individual'],check=True)
    elif a.mode=='pack':pack(a)
    else:merge(a)
if __name__=='__main__':main()
