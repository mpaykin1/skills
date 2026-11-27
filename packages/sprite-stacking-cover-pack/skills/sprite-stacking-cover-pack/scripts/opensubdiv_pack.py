"""Optional OpenSubdiv Loop CPU geometry candidate; no canonical volume changes."""
import argparse, json, math, shutil, subprocess, tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from open3d_stack import load_inputs, digest, native_to_world

SOURCE_NAMES=('native_mesh.npz','native_grid.npz','stack.json','geometry-source.json')

def hashes(root): return {n:digest(root/n) for n in SOURCE_NAMES}

def topology(v,f):
    if v.ndim!=2 or v.shape[1]!=3 or not len(v) or not np.isfinite(v).all(): raise ValueError('Invalid vertices')
    if f.ndim!=2 or f.shape[1]!=3 or not len(f) or f.dtype.kind not in 'iu' or f.min()<0 or f.max()>=len(v): raise ValueError('Invalid triangles')
    if len(np.unique(f))!=len(v) or len(np.unique(np.sort(f,axis=1),axis=0))!=len(f): raise ValueError('Unused vertices or duplicate triangles')
    cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    if np.any(np.linalg.norm(cross,axis=1)<=1e-14): raise ValueError('Degenerate triangle')
    edges=defaultdict(list); links=defaultdict(lambda:defaultdict(set))
    for a,b,c in f.tolist():
        for i,j,k in ((a,b,c),(b,c,a),(c,a,b)):
            edges[tuple(sorted((i,j)))].append((i,j))
            links[i][j].add(k); links[i][k].add(j)
    # Closed oriented manifold only; do not silently fix holes or bow ties.
    if any(len(e)!=2 or e[0]!=e[1][::-1] for e in edges.values()): raise ValueError('Require closed oriented manifold mesh')
    for link in links.values():
        if any(len(n)!=2 for n in link.values()): raise ValueError('Nonmanifold vertex link')
        pending=[next(iter(link))]; seen=set()
        while pending:
            j=pending.pop()
            if j not in seen: seen.add(j);pending.extend(link[j]-seen)
        if len(seen)!=len(link): raise ValueError('Disconnected vertex fan')
    # One connected shell only, with nonzero signed volume.
    pending=[0]; seen=set()
    while pending:
        i=pending.pop()
        if i not in seen: seen.add(i);pending.extend(set(links[i])-seen)
    if len(seen)!=len(v): raise ValueError("Multiple disconnected shells: process separately")
    q=v-v.mean(0); volume=np.einsum("ij,ij->i",q[f[:,0]],np.cross(q[f[:,1]],q[f[:,2]])).sum()/6
    if not np.isfinite(volume) or abs(volume)<1e-14: raise ValueError("Invalid enclosed volume")
    return edges,volume

def checks(v,f,refined,faces,xyz,step,level,creases):
    edges,volume=topology(v,f); new_edges,new_volume=topology(refined,faces)
    if volume*new_volume<=0: raise ValueError("Global winding reversed")
    if len(faces)!=len(f)*4**level: raise ValueError('Unexpected subdivision face count')
    if len(v)-len(edges)+len(f)!=len(refined)-len(new_edges)+len(faces): raise ValueError('Euler characteristic changed')
    if np.any(np.abs(refined.min(0)-v.min(0))>step) or np.any(np.abs(refined.max(0)-v.max(0))>step): raise ValueError('Bounding box drift exceeds one native voxel')
    # Bounded sampled proximity, not exact Hausdorff distance or self-intersection proof.
    samples=np.concatenate([refined, refined[faces].mean(1)])
    dist=cKDTree(xyz).query(samples)[0]; peak=float(dist.max())
    if peak>1.75*step: raise ValueError('Refined surface too far from native material grid')
    # A tagged infinite-sharp edge must retain sampled points of the original segment.
    if creases:
        t=np.linspace(0,1,2**level+1)[:,None]; a=np.asarray(creases,dtype=int)
        expected=(v[a[:,0],None,:]*(1-t)+v[a[:,1],None,:]*t).reshape(-1,3)
        if np.max(cKDTree(refined).query(expected)[0])>max(step*.02, np.max(np.abs(v))*2e-6,1e-8): raise ValueError('Tagged crease moved; keep source')
    return peak

def read_result(path,max_faces):
    with Path(path).open() as inp:
        nv,nf=map(int,inp.readline().split())
        if not 3<=nv<=3*max_faces or not 1<=nf<=max_faces: raise ValueError('Bad output counts')
        def block(n,cast):
            rows=[]
            for _ in range(n):
                line=inp.readline().split()
                if len(line)!=3: raise ValueError('Bad output row')
                rows.append([cast(x) for x in line])
            return np.asarray(rows)
        v=block(nv,float);f=block(nf,int)
        if inp.read().strip(): raise ValueError('Extra output')
    return v,f

def load_candidate(root,candidate,v,f,xyz,step):
    candidate=Path(candidate).resolve(); m=json.loads((candidate/'subdiv.json').read_text()); p=candidate/'subdiv-mesh.npz'
    if m.get('schema')!='cover-pack-opensubdiv/1' or m.get('sourceSHA256')!=hashes(root) or m.get('meshSHA256')!=digest(p) or m.get('level') not in (1,2): raise ValueError('Subdivision candidate provenance mismatch')
    with np.load(p,allow_pickle=False) as a: vv=a['vertices']; ff=a['faces']
    checks(v,f,vv,ff,xyz,step,m['level'],m['creases']);return vv,ff,m

def run(asset,out,exe,level,crease_file):
    root=Path(asset).resolve();out=Path(out).resolve()
    if out.exists() or root in out.parents or out in root.parents: raise ValueError('Separate new output required')
    meta,v,f,xyz,rgba,step=load_inputs(root); source=hashes(root)
    if len(v)>200000 or len(f)>200000 or len(f)*4**level>1000000: raise ValueError('Subdivision mesh budget exceeded')
    if np.any(rgba[:,3]<1-1e-6): raise ValueError('Opaque static closed mesh only; keep transparent or open assets')
    edges,_=topology(v,f); creases=json.loads(Path(crease_file).read_text()) if crease_file else []
    if not isinstance(creases,list) or any(not isinstance(e,list) or len(e)!=2 or any(type(i)!=int for i in e) or tuple(sorted(e)) not in edges for e in creases): raise ValueError('Creases must be explicit existing native edges')
    creases=sorted(set(tuple(sorted(e)) for e in creases))
    # Sharp edge chains may move at endpoints/junctions; postcheck rejects this, rather than claiming exact preservation.
    tool=shutil.which(exe)
    if not tool: raise RuntimeError('Build real OpenSubdiv CPU bridge first; no substitute subdivision')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as td:
        tmp=Path(td); inp=tmp/'input.txt'; result=tmp/'output.txt'; stage=tmp/'candidate';stage.mkdir()
        with inp.open('w') as s:
            s.write(f'{len(v)} {len(f)} {len(creases)} {level}\n');np.savetxt(s,v,fmt='%.17g');np.savetxt(s,f,fmt='%d')
            for i,j in creases:s.write(f'{i} {j} 10\n')
        subprocess.run([tool,str(inp),str(result)],check=True,timeout=300)
        vv,ff=read_result(result,len(f)*4**level); peak=checks(v,f,vv,ff,xyz,step,level,creases)
        if hashes(root)!=source: raise ValueError('Source changed')
        mesh=stage/'subdiv-mesh.npz';np.savez_compressed(mesh,vertices=vv,faces=ff)
        obj=stage/'subdiv-mesh.obj'
        with obj.open('w') as s:
            for p in native_to_world(vv,meta['nativeUp']):s.write('v %.17g %.17g %.17g\n'%tuple(p))
            for t in ff+1:s.write('f %d %d %d\n'%tuple(t))
        (stage/'subdiv.json').write_text(json.dumps({'schema':'cover-pack-opensubdiv/1','sourceSHA256':source,'meshSHA256':digest(mesh),'objSHA256':digest(obj),'bridgeSHA256':digest(tool),'algorithm':'OpenSubdiv Far Loop CPU','level':level,'creases':creases,'nativeUp':meta['nativeUp'],'pivot':meta['pivot'],'gridOrigin':meta['gridOrigin'],'sourceTriangles':len(f),'candidateTriangles':len(ff),'maxSampleToGrid':peak,'status':'review-required; static geometry candidate only'},indent=2)+'\n')
        stage.rename(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--asset',required=True);p.add_argument('--out',required=True);p.add_argument('--exe',default='cover-opensubdiv');p.add_argument('--level',type=int,choices=[1,2],default=1);p.add_argument('--creases');p.add_argument('--static-reviewed',action='store_true',required=True,help='Confirm source is approved static geometry, not rigged or morphing');a=p.parse_args();run(a.asset,a.out,a.exe,a.level,a.creases)
