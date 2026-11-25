"""OpenVDB interchange for existing RGBA stacks and independent density volumes.
Never fill a surface, replace source materials or interpret object opacity as smoke.
Requires a real OpenVDB Python build with NumPy support for VDB I/O.
"""
import argparse, hashlib, json, re
from pathlib import Path
import numpy as np
from PIL import Image


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d): Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def backend():
    try: import openvdb as vdb
    except ImportError:
        try: import pyopenvdb as vdb
        except ImportError as e: raise RuntimeError('Install official OpenVDB Python bindings with NumPy support; no simulated VDB output') from e
    if not hasattr(vdb.FloatGrid(),'copyFromArray') or not hasattr(vdb.FloatGrid(),'copyToArray'):
        raise RuntimeError('OpenVDB must be built with NumPy array support')
    return vdb

def separate(root,out):
    root=Path(root).resolve();out=Path(out).resolve()
    if out.exists() or root==out or root in out.parents: raise ValueError('Use a new output directory outside source')
    return root,out

def load_stack(root,max_cells):
    m=read(root/'stack.json');n=int(m['size']);d=int(m['layerCount']);s=np.asarray(m['spacing'],float);a=np.asarray(m['gridOrigin'],float)
    if not (1<=n<=1024 and 1<=d<=1024 and n*n*d<=max_cells and s.shape==(3,) and np.isfinite(s).all() and np.all(s>0) and np.allclose(s,s[0]) and a.shape==(3,) and np.isfinite(a).all()): raise ValueError('Invalid grid or cell budget exceeded')
    if m['layerOrder']!='bottom-to-top' or m['layers']!=[f'layers/{z:04d}.png' for z in range(d)]: raise ValueError('Unexpected layer order or paths')
    return m,n,d,float(s[0]),a

def plane_to_xyz(p):
    # PNG +Y up -> array [X,Y,Z], preserving RGB and alpha independently.
    return np.ascontiguousarray(p[::-1].T[:,:,None],dtype=np.float32)/255

def xyz_to_plane(p): return np.rint(np.clip(p[:,:,0].T[::-1],0,1)*255).astype(np.uint8)

def density_to_alpha(density,step,extinction):
    if not np.isfinite(density).all() or np.any(density<0) or not np.isfinite(step) or step<=0 or not np.isfinite(extinction) or extinction<=0: raise ValueError('Invalid nonnegative density or optical parameters')
    return -np.expm1(-density.astype(np.float64)*step*extinction)

def transform(vdb,step,center):
    # OpenVDB uses row-vector 4x4 matrix with translation in the final row.
    m=np.eye(4);m[:3,:3]*=step;m[3,:3]=center
    t=vdb.createLinearTransform(m.tolist())
    if not np.allclose(t.indexToWorld((0,0,0)),center) or not np.allclose(t.indexToWorld((1,1,1)),center+step): raise ValueError('OpenVDB transform convention mismatch')
    return t

def rgba_archive(src,out,max_cells=64_000_000):
    src,out=separate(src,out);m,n,d,step,anchor=load_stack(src,max_cells);vdb=backend()
    t=transform(vdb,step,anchor+step/2);grids=[]
    for name in ('red','green','blue','alpha'):
        g=vdb.FloatGrid();g.name=name;g.transform=t;grids.append(g)
    hashes=[]
    for z,rel in enumerate(m['layers']):
        p=src/rel;im=np.asarray(Image.open(p).convert('RGBA'))
        if im.shape!=(n,n,4): raise ValueError('Invalid PNG layer dimensions')
        hashes.append(digest(p))
        for c,g in enumerate(grids): g.copyFromArray(plane_to_xyz(im[:,:,c]),ijk=(0,0,z))
    out.mkdir(parents=True);file=out/'surface.vdb';vdb.write(str(file),grids=grids)
    # Real read-back of every channel, transform and layer before declaring archive valid.
    for c,g in enumerate(grids):
        restored=vdb.read(str(file),g.name)
        if not np.allclose(restored.transform.indexToWorld((0,0,0)),anchor+step/2) or not np.allclose(restored.transform.indexToWorld((1,1,1)),anchor+step*1.5): raise ValueError('Roundtrip transform mismatch')
        for z,rel in enumerate(m['layers']):
            arr=np.zeros((n,n,1),np.float32);restored.copyToArray(arr,ijk=(0,0,z))
            if not np.array_equal(xyz_to_plane(arr),np.asarray(Image.open(src/rel).convert('RGBA'))[:,:,c]): raise ValueError('VDB RGBA roundtrip mismatch')
    meta={'schema':'cover-pack-openvdb/1','kind':'rgba-surface-or-solid','file':'surface.vdb','grids':['red','green','blue','alpha'],'size':[n,n,d],'spacing':[step]*3,'gridOrigin':anchor.tolist(),'pivot':m['pivot'],'sourceStackSHA256':digest(src/'stack.json'),'sourceLayerSHA256':hashes,'vdbSHA256':digest(file),'rgbaRoundtrip':'exact','status':'prototype','representation':m.get('representation'),'sourceRetained':True}
    write(out/'volume.json',meta);return meta

def density_stack(file,grid_name,out,tint,extinction,max_cells=64_000_000):
    file=Path(file).resolve();out=Path(out).resolve()
    if out.exists(): raise FileExistsError(out)
    vdb=backend();g=vdb.read(str(file),grid_name)
    if not isinstance(g,vdb.FloatGrid) or g.background!=0 or g.gridClass!=vdb.GridClass.FOG_VOLUME: raise ValueError('Require a zero-background scalar FOG_VOLUME grid, not an SDF or object alpha')
    o=np.asarray(g.transform.indexToWorld((0,0,0)),float);basis=np.column_stack([np.asarray(g.transform.indexToWorld(tuple(int(k==i) for k in range(3))))-o for i in range(3)])
    step=float(basis[0,0]);
    if step<=0 or not np.allclose(basis,np.eye(3)*step) or not np.isfinite(o).all(): raise ValueError('Resample rotated or nonuniform grid upstream; do not guess alignment')
    lo,hi=(np.asarray(x,dtype=int) for x in g.evalActiveVoxelBoundingBox());dims=hi-lo+1
    if np.any(dims<=0) or np.any(dims>1024) or int(np.prod(dims,dtype=np.int64))>max_cells: raise ValueError('Empty density grid or cell budget exceeded')
    tint=np.asarray(tint,dtype=int)
    if tint.shape!=(3,) or np.any(tint<0) or np.any(tint>255): raise ValueError('RGB tint must be 0..255')
    side=int(max(dims[:2]));d=int(dims[2]);
    if side*side*d>max_cells: raise ValueError('Padded density exceeds cell budget')
    pad=(side-dims[:2])//2;start=lo.copy();start[:2]-=pad
    out.mkdir(parents=True);(out/'layers').mkdir();layers=[]
    for z in range(d):
        p=np.zeros((side,side,1),np.float32);ijk=(int(start[0]),int(start[1]),int(start[2])+z)
        g.copyToArray(p,ijk=ijk);alpha=density_to_alpha(p,step,extinction)
        im=np.zeros((side,side,4),np.uint8);im[:,:,3]=xyz_to_plane(alpha);im[im[:,:,3]>0,:3]=tint
        rel=f'layers/{z:04d}.png';Image.fromarray(im).save(out/rel);layers.append(rel)
    anchor=o+(start-.5)*step
    meta={'format':'rgba-horizontal-layers','kind':'atmosphere-density','layers':layers,'size':side,'tileSize':[side,side],'layerCount':d,'layerOrder':'bottom-to-top','spacing':[step]*3,'gridOrigin':anchor.tolist(),'pivot':[0,0,-d*step/2],'pivotConvention':'offset from center to bottom center','axes':'+X right, +Y top of PNG, +Z up','densityGrid':grid_name,'sourceVDBSHA256':digest(file),'extinction':extinction,'tintRGB':tint.tolist(),'representation':'density integrated over one voxel step; render with depth-aware alpha or raymarch','collision':None,'status':'prototype'}
    write(out/'stack.json',meta);write(out/'asset.json',{**meta,'id':out.name});return meta

def batch(generated,refined,out,max_cells):
    generated,out=separate(generated,out);refined=Path(refined).resolve() if refined else None
    if refined and (refined==out or refined in out.parents): raise ValueError('Output must not modify refinement')
    gen=read(generated/'generation.json');ids=gen['assets'];valid=lambda i:isinstance(i,str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',i)
    if not ids or len(set(ids))!=len(ids) or not all(valid(i) for i in ids): raise ValueError('Invalid asset IDs')
    records={}
    if refined:
        ref=read(refined/'refinement.json')
        if ref['generationSHA256']!=digest(generated/'generation.json'): raise ValueError('Refinement from different generation')
        records={r['id']:r for r in ref['assets']}
        if set(records)!=set(ids): raise ValueError('Refinement asset set mismatch')
    out.mkdir(parents=True);result=[]
    for i in ids:
        src=generated/i;mode='native'
        if refined:
            r=records[i];candidate=refined/i;a=read(candidate/'geometry-audit.json')
            if a['sourceGridSHA256']!=digest(src/'native_grid.npz') or a['sourceMeshSHA256']!=digest(src/'native_mesh.npz'): raise ValueError('Refinement source mismatch: '+i)
            if r['mode']=='solid':
                if not a['solidEligible'] or a['mode']!='solid': raise ValueError('Invalid solid candidate')
                src=candidate;mode='solid'
            elif r['mode']!='audit': raise ValueError('Unknown refinement mode')
        rgba_archive(src,out/i,max_cells);result.append({'id':i,'sourceMode':mode,'volume':f'{i}/volume.json'})
    write(out/'volumes.json',{'generationSHA256':digest(generated/'generation.json'),'refinementSHA256':digest(refined/'refinement.json') if refined else None,'assets':result,'status':'prototype'})

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    for mode in ('archive','batch','density'):
        s=sub.add_parser(mode);s.add_argument('--out',required=True);s.add_argument('--max-cells',type=int,default=64_000_000)
        if mode=='archive': s.add_argument('--asset',required=True)
        elif mode=='batch': s.add_argument('--generated',required=True);s.add_argument('--refined')
        else:
            s.add_argument('--vdb',required=True);s.add_argument('--grid',default='density');s.add_argument('--tint',type=int,nargs=3,required=True);s.add_argument('--extinction',type=float,required=True)
    a=p.parse_args()
    if a.mode=='archive': rgba_archive(a.asset,a.out,a.max_cells)
    elif a.mode=='batch': batch(a.generated,a.refined,a.out,a.max_cells)
    else: density_stack(a.vdb,a.grid,a.out,a.tint,a.extinction,a.max_cells)
if __name__=='__main__':main()
