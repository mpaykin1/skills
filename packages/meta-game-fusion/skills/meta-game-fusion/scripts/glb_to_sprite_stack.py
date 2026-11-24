#!/usr/bin/env python3
"""Author-approved *static watertight* GLB -> true horizontal PNG volume slices.

Optional: trimesh, scipy, Pillow, numpy. No original model is modified.
Imported animation/skin/morph GLBs are strictly refused; animate only from full
artist-approved pose volumes. GLB texture colors are approximated by nearest
surface vertex UV, so this output is a preview until checked from all angles.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct,sys
from pathlib import Path
import numpy as np
from PIL import Image


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_glb_static(path: Path):
    raw=path.read_bytes()
    if len(raw)<20 or raw[:4]!=b'glTF' or struct.unpack_from('<I',raw,4)[0]!=2 or struct.unpack_from('<I',raw,8)[0]!=len(raw):
        raise ValueError('Expected valid GLB v2, not arbitrary executable input')
    size,kind=struct.unpack_from('<I4s',raw,12)
    if kind!=b'JSON' or size<=0 or 20+size>len(raw):raise ValueError('GLB JSON chunk missing')
    j=json.loads(raw[20:20+size].decode('utf-8'))
    if j.get('animations') or j.get('skins') or any(p.get('targets') for m in j.get('meshes',[]) for p in m.get('primitives',[])):
        raise ValueError('Animated/skinned/morphed GLB: requires independently approved pose stacks; cannot flatten')
    return j


def bake(src:Path,out:Path,ident:str,digest:str,license:str,slices:int,tile:int):
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,42}',ident):raise ValueError('Unsafe asset id')
    if not 32<=tile<=256 or not 16<=slices<=128:raise ValueError('Mobile volume budget: tile32..256 slices16..128')
    if src.is_symlink() or not src.is_file() or src.suffix.lower()!='.glb' or src.stat().st_size>90_000_000:
        raise ValueError('Invalid/symlink/oversize model')
    if sha256(src)!=digest:raise ValueError('Source GLB SHA256 mismatch')
    check_glb_static(src)
    if out.exists():raise ValueError('Never overwrite existing sprite stack path')
    import trimesh
    from scipy.spatial import cKDTree
    loaded=trimesh.load(src,force='scene',process=False)
    mesh=loaded.to_geometry() if isinstance(loaded,trimesh.Scene) else loaded
    if not isinstance(mesh,trimesh.Trimesh) or len(mesh.faces)<4 or len(mesh.faces)>400000:
        raise ValueError('Unsupported/oversized static GLB mesh')
    if not mesh.is_watertight:
        raise ValueError('Source GLB is nonwatertight; cannot invent physical interior volume')
    bounds=mesh.bounds.astype(np.float64)
    dims=bounds[1]-bounds[0]
    if not np.all(np.isfinite(dims)) or np.any(dims<=.005) or max(dims)>60:
        raise ValueError('GLB bounds degenerate or over safe limit')
    # Voxelize a REAL closed mesh at a pitch suited to the tallest detailed axis;
    # grid occupancy is sampled onto every output slice, independent of camera.
    pitch=min(dims[0]/(tile-8),dims[2]/(tile-8),dims[1]/(slices-4))
    pitch=max(pitch,max(dims)/300)
    voxel=mesh.voxelized(pitch=pitch).fill()
    count=np.prod(voxel.shape)
    if count>24_000_000:raise ValueError('Source volume too dense for sprite slicing')
    xs=np.linspace(bounds[0,0],bounds[1,0],tile,endpoint=False,dtype=np.float64)+dims[0]/tile/2
    zs=np.linspace(bounds[1,2],bounds[0,2],tile,endpoint=False,dtype=np.float64)-dims[2]/tile/2
    X,Z=np.meshgrid(xs,zs)
    posxy=np.column_stack([X.ravel(),Z.ravel()])
    vertex=mesh.vertices
    tree=cKDTree(vertex)
    source_colors=np.asarray(mesh.visual.vertex_colors) if mesh.visual.kind in ('vertex','face') else None
    tex=None;uv=None
    if mesh.visual.kind=='texture':
        uv=np.asarray(mesh.visual.uv)
        im=getattr(mesh.visual.material,'image',None)
        if im is not None:
            tex=np.asarray(im.convert('RGBA'))
    folder=out/ident/'layers'
    folder.mkdir(parents=True)
    coverage=[]
    for li in range(slices):
        yy=bounds[0,1]+(li+.5)*dims[1]/slices
        pts=np.column_stack([posxy[:,0],np.full(len(posxy),yy),posxy[:,1]])
        occupied=voxel.is_filled(pts).reshape(tile,tile)
        rgb=np.empty((tile,tile,4),dtype=np.uint8)
        rgb[:,:,:]=[110,113,111,0]
        if occupied.any():
            q=pts[occupied.ravel()]
            _,inds=tree.query(q,k=1,workers=1)
            if tex is not None and uv is not None and len(uv)==len(vertex):
                coords=uv[inds];h,w=tex.shape[:2]
                px=np.clip(np.rint(coords[:,0]*(w-1)).astype(int),0,w-1)
                py=np.clip(np.rint((1-coords[:,1])*(h-1)).astype(int),0,h-1)
                cc=tex[py,px]
            elif source_colors is not None and len(source_colors)==len(vertex):
                cc=source_colors[inds]
            else:
                # An untextured GLB has no authored texture; retain neutral mesh tone.
                cc=np.tile(np.array([115,119,122,255],dtype=np.uint8),(len(inds),1))
            flat=rgb.reshape(-1,4)
            flat[occupied.ravel(),:3]=cc[:,:3]
            flat[occupied.ravel(),3]=255
        coverage.append(int(occupied.sum()))
        Image.fromarray(rgb,'RGBA').save(folder/f'{li:03d}.png')
    if sum(c>0 for c in coverage)<slices//3:
        raise ValueError('Too many blank source slices; reject generated object')
    stack={'dimensions':[float(dims[0]),float(dims[1]),float(dims[2])],
           'pivot':[0,0,0],'origin':'watertight-authorized-GLB',
           'source_glb_sha256':digest,'approved_for_reuse':True,
           'license':license,'texture_sampling':'nearest-vertex-UV-preview',
           'requires_multiview_artist_approval':True,
           'source_model_preserved':str(src.name)}
    (folder.parent/'stack.json').write_text(json.dumps(stack,indent=2,ensure_ascii=False)+'\n','utf-8')
    return {'asset':ident,'slices':slices,'source_sha256':digest,'preview_needs_approval':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--glb',required=True)
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--id',required=True)
    p.add_argument('--license',required=True,choices=['CC0-1.0','CC-BY-4.0','MIT','proprietary-user-owned','approved-private'])
    p.add_argument('--approved',action='store_true')
    p.add_argument('--slices',type=int,default=72)
    p.add_argument('--tile',type=int,default=96)
    args=p.parse_args()
    if not args.approved:p.error('Source asset owner must explicitly approve converting this model')
    try:print(json.dumps(bake(Path(args.glb),Path(args.out),args.id,args.source_sha256,args.license,args.slices,args.tile)))
    except (ValueError,OSError,TypeError) as e:p.exit(2,str(e)+'\n')

if __name__=='__main__':main()
