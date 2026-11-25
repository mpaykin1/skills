"""Open3D geometry audit / optional opaque solid stack from matching TRELLIS source.
Never overwrite the native grid or its exported RGBA surface layers.
"""
import argparse, hashlib, json, shutil
from pathlib import Path
import numpy as np
from PIL import Image


def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def write(p,d): Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def world_to_native(xyz,up):
    if up=='z': return xyz
    if up=='y': return xyz[:,[0,2,1]]*[1,1,-1]
    raise ValueError('Unknown native axis')


def native_to_world(xyz,up):
    if up=='z': return xyz
    if up=='y': return xyz[:,[0,2,1]]*[1,-1,1]
    raise ValueError('Unknown native axis')


def load_inputs(root):
    meta=read(root/'stack.json'); binding=read(root/'geometry-source.json')
    for name in ('native_grid.npz','native_mesh.npz'):
        if digest(root/name)!=binding[name]: raise ValueError('Native source changed: '+name)
    with np.load(root/'native_mesh.npz',allow_pickle=False) as m:
        v=np.asarray(m['vertices'],np.float64); f=np.asarray(m['faces'])
    if v.ndim!=2 or v.shape[1]!=3 or not len(v) or not np.isfinite(v).all(): raise ValueError('Invalid vertices')
    if f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(v): raise ValueError('Invalid faces')
    with np.load(root/'native_grid.npz',allow_pickle=False) as g:
        c=np.asarray(g['coords'],np.float64); rgba=np.asarray(g['rgba'],np.float32); step=float(g['voxel_size']); origin=np.asarray(g['origin'])
    if c.ndim!=2 or c.shape[1]!=3 or rgba.shape!=(len(c),4) or not len(c) or not np.isfinite(c).all() or not np.isfinite(rgba).all() or not np.isfinite(step) or step<=0: raise ValueError('Invalid grid')
    xyz=(c+.5)*step+origin
    lo,hi=xyz.min(0),xyz.max(0)
    # Reject frame/scale mismatches, including GLB normalization. Native source can differ a few cells.
    if np.any(np.abs(v.min(0)-lo)>4*step) or np.any(np.abs(v.max(0)-hi)>4*step): raise ValueError('Mesh and O-Voxel bounds disagree; no guessed alignment')
    n=int(meta['size']); depth=int(meta['layerCount']); spacing=np.asarray(meta['spacing'],float); anchor=np.asarray(meta['gridOrigin'],float)
    if not (1<=n<=1024 and 1<=depth<=1024 and spacing.shape==(3,) and np.all(spacing>0) and np.allclose(spacing,spacing[0]) and anchor.shape==(3,) and np.isfinite(anchor).all()): raise ValueError('Invalid stack grid')
    if len(meta['layers'])!=depth or meta['layerOrder']!='bottom-to-top': raise ValueError('Invalid layer order')
    for i,p in enumerate(meta['layers']):
        if p!=f'layers/{i:04d}.png': raise ValueError('Unexpected layer path')
    return meta,v,f,xyz,rgba,step


def points_for_layer(anchor,step,n,z):
    # PNG row 0 is +Y; retain exact world coordinates and center convention.
    y,x=np.indices((n,n),dtype=np.float64)
    return np.stack([anchor[0]+(x+.5)*step,anchor[1]+(n-y-.5)*step,np.full_like(x,anchor[2]+(z+.5)*step)],axis=-1).reshape(-1,3)


def run(root,out,mode,max_cells=64_000_000):
    root=Path(root).resolve();out=Path(out).resolve()
    if out.exists(): raise FileExistsError(out)
    if root==out or root in out.parents: raise ValueError('Output must be separate from native asset directory')
    meta,v,f,xyz,rgba,native_step=load_inputs(root)
    import open3d as o3d
    mesh=o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(v),o3d.utility.Vector3iVector(f.astype(np.int32)))
    # No destructive mesh repair, topology is assessed on the exact native mesh.
    topology={'watertight':bool(mesh.is_watertight()),'edgeManifold':bool(mesh.is_edge_manifold(allow_boundary_edges=False)), 'vertexManifold':bool(mesh.is_vertex_manifold()),'selfIntersecting':bool(mesh.is_self_intersecting())}
    opaque=bool(np.all(rgba[:,3]>=1-1e-6)); solid_ok=topology['watertight'] and topology['edgeManifold'] and topology['vertexManifold'] and not topology['selfIntersecting'] and opaque
    scene=o3d.t.geometry.RaycastingScene();scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))
    # Distance diagnostic using original native grid (sample deterministically for bounded RAM).
    sample=xyz[::max(1,int(np.ceil(len(xyz)/100000)))]
    dist=scene.compute_distance(o3d.core.Tensor(sample.astype(np.float32))).numpy()
    audit={'schema':'cover-pack-open3d/1','status':'prototype','open3dVersion':o3d.__version__,'mode':mode,'topology':topology,'allOpaque':opaque,'solidEligible':solid_ok,'surfaceDistanceP95':float(np.percentile(dist,95)),'nativeVoxelSize':native_step,'sourceGridSHA256':digest(root/'native_grid.npz'),'sourceMeshSHA256':digest(root/'native_mesh.npz')}
    if mode=='solid' and not solid_ok: raise ValueError('Solid export blocked: mesh must be watertight, manifold, non-self-intersecting and entirely opaque; use audit/native stack')
    if mode=='solid' and audit['surfaceDistanceP95']>3*native_step: raise ValueError('Solid export blocked: native material grid deviates from mesh')
    if mode=='audit':
        out.mkdir(parents=True);write(out/'geometry-audit.json',audit);return audit
    n=int(meta['size']);depth=int(meta['layerCount']);step=float(meta['spacing'][0]);anchor=np.asarray(meta['gridOrigin']);up=meta['nativeUp']
    if n*n*depth>max_cells: raise ValueError('Solid volume exceeds cell budget; reduce resolution explicitly')
    # The interior receives nearest native RGB only; existing surface RGBA is untouched.
    from scipy.spatial import cKDTree
    tree=cKDTree(xyz);added=0
    out.mkdir(parents=True);(out/'layers').mkdir()
    for z,rel in enumerate(meta['layers']):
        img=np.asarray(Image.open(root/rel).convert('RGBA')).copy()
        if img.shape!=(n,n,4): raise ValueError('Source layer size mismatch')
        q=world_to_native(points_for_layer(anchor,step,n,z),up)
        empty=np.flatnonzero(img.reshape(-1,4)[:,3]==0)
        for k in range(0,len(empty),65536):
            ix=empty[k:k+65536];pts=q[ix]
            t=o3d.core.Tensor(pts.astype(np.float32));inside=scene.compute_occupancy(t,nsamples=3).numpy()>0.5
            # Fill only deeper interior, avoiding thin details and material boundaries.
            sd=scene.compute_signed_distance(t,nsamples=3).numpy()
            ids=ix[inside & (sd < -step*.5)]
            if len(ids):
                _,near=tree.query(q[ids]);pixels=img.reshape(-1,4);pixels[ids,:3]=np.rint(np.clip(rgba[near,:3],0,1)*255).astype(np.uint8);pixels[ids,3]=255;added+=len(ids)
        Image.fromarray(img).save(out/rel)
    audit['addedInteriorCells']=added
    revised={**meta,'representation':'opaque solid candidate; original surface retained; inferred interior RGB','status':'prototype','geometryAudit':'geometry-audit.json','sourceGridSHA256':audit['sourceGridSHA256']}
    write(out/'stack.json',revised);write(out/'asset.json',{**revised,'id':root.name,'preview':None});write(out/'geometry-audit.json',audit)
    return audit


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--asset',required=True);p.add_argument('--out',required=True);p.add_argument('--mode',choices=['audit','solid'],default='audit');p.add_argument('--max-cells',type=int,default=64_000_000);a=p.parse_args();run(a.asset,a.out,a.mode,a.max_cells)

if __name__=='__main__':main()
