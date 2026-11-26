#!/usr/bin/env python3
"""Original static GLB to actual RGBA sprite stacking slices.

Open3D CPU raycasting is preferred when installed; legacy trimesh voxelization
is preserved and selectable. Original GLB, original UV/color and gameplay are
never overwritten or replaced; visuals are separate derivatives only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np
from PIL import Image
import trimesh
from scipy.spatial import cKDTree

MAX_FACES=400_000
MAX_CELLS=6_000_000
MAX_FILLED=1_000_000


def glb_info(path:Path)->dict:
    with path.open('rb') as fp:
        header=fp.read(20)
        if len(header)!=20 or header[:4]!=b'glTF' or struct.unpack_from('<I',header,4)[0]!=2:
            raise ValueError('Expected original glTF 2.0 .glb')
        if struct.unpack_from('<I',header,16)[0]!=0x4e4f534a:
            raise ValueError('GLB JSON chunk missing')
        length=struct.unpack_from('<I',header,12)[0]
        if length>32_000_000:
            raise ValueError('GLB JSON metadata too large')
        return json.loads(fp.read(length))


def materials(mesh:trimesh.Trimesh):
    kind=mesh.visual.kind
    if kind=='vertex':
        rgba=np.asarray(mesh.visual.vertex_colors,dtype=np.uint8)
        if rgba.shape!=(len(mesh.vertices),4):raise ValueError('Invalid original vertex colors')
        return {'mode':'vertex','vertex':rgba}
    if kind=='face':
        rgba=np.asarray(mesh.visual.face_colors,dtype=np.uint8)
        return {'mode':'face','face':rgba}
    if kind=='texture':
        uv=np.asarray(mesh.visual.uv)
        if uv.ndim!=2 or uv.shape!=(len(mesh.vertices),2):
            raise ValueError('Original UV0 mapping unavailable')
        mat=mesh.visual.material
        img=getattr(mat,'baseColorTexture',None)
        if img is None:img=getattr(mat,'image',None)
        factor=getattr(mat,'baseColorFactor',None)
        if factor is None:factor=getattr(mat,'diffuse',None)
        if factor is None:factor=np.array([255,255,255,255])
        factor=np.asarray(factor,dtype=float).ravel()
        if len(factor)==3:factor=np.append(factor,255.)
        if len(factor)!=4:factor=np.array([255,255,255,255],dtype=float)
        if np.max(factor)<=1:factor=factor*255
        if img is None:return {'mode':'constant','color':np.clip(factor,0,255).astype('uint8')}
        rgba=np.asarray(img.convert('RGBA'),dtype=np.uint8)
        return {'mode':'texture','uv':uv,'pixels':rgba,'factor':factor/255}
    raise ValueError('Original mesh has no authored colors/material: refusing placeholder conversion')


def colors_at(mesh,points,spec,neighbors=12,chunk=3072,with_distance=False):
    triangles=np.asarray(mesh.vertices,dtype=np.float64)[mesh.faces]
    centers=triangles.mean(axis=1)
    tree=cKDTree(centers)
    result=np.empty((len(points),4),dtype=np.uint8)
    best=np.empty(len(points),dtype=np.float64) if with_distance else None
    k=min(max(1,neighbors),len(triangles))
    for start in range(0,len(points),chunk):
        end=min(len(points),start+chunk)
        query=np.asarray(points[start:end],dtype=np.float64)
        _,indices=tree.query(query,k=k)
        indices=np.asarray(indices).reshape(len(query),k)
        tri=triangles[indices.reshape(-1)]
        pts=np.repeat(query,k,axis=0)
        nearest=trimesh.triangles.closest_point(tri,pts).reshape(len(query),k,3)
        distances=np.sum((nearest-query[:,None,:])**2,axis=-1)
        selected=np.argmin(distances,axis=1)
        if best is not None:best[start:end]=distances[np.arange(len(query)),selected]
        face_index=indices[np.arange(len(query)),selected]
        nearest_pt=nearest[np.arange(len(query)),selected]
        if spec['mode']=='face':
            color=spec['face'][face_index].astype(float)
        else:
            bary=trimesh.triangles.points_to_barycentric(triangles[face_index],nearest_pt)
            bary=np.clip(bary,0,1)
            bary/=np.maximum(1e-10,bary.sum(axis=1,keepdims=True))
            if spec['mode']=='vertex':
                color=(spec['vertex'][mesh.faces[face_index]].astype(float)*bary[:,:,None]).sum(axis=1)
            elif spec['mode']=='constant':
                color=np.broadcast_to(spec['color'],(len(query),4)).astype(float)
            elif spec['mode']=='texture':
                uv=(spec['uv'][mesh.faces[face_index]]*bary[:,:,None]).sum(axis=1)%1.0
                image=spec['pixels'];h,w=image.shape[:2]
                px=np.clip(np.floor(uv[:,0]*w).astype(int),0,w-1)
                py=np.clip(np.floor((1.0-uv[:,1])*h).astype(int),0,h-1)
                color=image[py,px].astype(float)*spec['factor']
            else:raise ValueError('Unsupported original visual')
        result[start:end]=np.clip(np.rint(color),0,255).astype('uint8')
    return (result,best) if with_distance else result


def convert(source:Path,out:Path,xy=192,z=96,allow_shell=False,voxelizer='auto',manifold='audit'):
    source=source.expanduser().resolve(strict=True)
    out=out.expanduser().resolve()
    if source.suffix.lower()!='.glb':raise ValueError('Source must be original GLB')
    if out==source or source in out.parents or out in source.parents:
        raise ValueError('Source and output must not overlap')
    if out.exists() and any(out.iterdir()):raise ValueError('Output folder must be empty')
    info=glb_info(source)
    if info.get('animations') or info.get('skins'):
        raise ValueError('Animated/skinned GLB cannot be frozen: use original full-pose animation or native GLB')
    if 'KHR_texture_basisu' in (info.get('extensionsRequired') or []):
        raise ValueError('Provide original PNG-textured GLB, not KTX2-only source')
    for mat in info.get('materials',[]):
        if mat.get('alphaMode')=='BLEND' or 'KHR_materials_transmission' in mat.get('extensions',{}):
            raise ValueError('Translucent material cannot retain its appearance as binary sprite stacking; use GLB renderer')
    scene=trimesh.load(source,force='scene',process=False)
    meshes=[m for m in scene.dump() if isinstance(m,trimesh.Trimesh) and len(m.faces)>0]
    if not meshes or sum(len(m.faces) for m in meshes)>MAX_FACES:
        raise ValueError('GLB has zero or too many mesh faces for CPU sprite stacking')
    specs=[materials(m) for m in meshes]
    from manifold_geometry import prepare as manifold_prepare
    occupancy_meshes,manifold_meta=manifold_prepare(meshes,manifold)
    if any(not m.is_watertight for m in occupancy_meshes) and not allow_shell:
        raise ValueError('Non-watertight mesh: refuse invented interior; use --allow-shell')
    points=np.vstack([m.vertices for m in meshes])
    if not np.isfinite(points).all():raise ValueError('Mesh contains invalid coordinates')
    lower=points.min(axis=0);upper=points.max(axis=0)
    size=np.maximum(upper-lower,1e-8)
    pitch=max(float(size[0])/max(2,xy-2),float(size[1])/max(2,xy-2),float(size[2])/max(2,z-2))
    shape=np.maximum(1,np.ceil(size/pitch).astype(int)+4)
    if int(np.prod(shape,dtype=np.int64))>MAX_CELLS or shape[0]>xy+4 or shape[1]>xy+4 or shape[2]>z+4:
        raise ValueError('Voxel budget exceeded; reduce --xy/--z')
    origin=lower-2*pitch
    grid=np.zeros((int(shape[2]),int(shape[1]),int(shape[0]),4),dtype=np.uint8)
    from open3d_voxelizer import available,voxel_points
    if voxelizer not in ('auto','open3d','trimesh'):
        raise ValueError('Unknown voxelizer')
    backend=('open3d' if available() else 'trimesh') if voxelizer=='auto' else voxelizer
    if backend=='open3d' and not available():
        raise RuntimeError('Open3D unavailable: install the official open3d Python package or select --voxelizer trimesh')
    used=0
    for index,mesh in enumerate(occupancy_meshes):
        if backend=='open3d':
            cellpoints=voxel_points(mesh,origin,pitch,shape,allow_shell=allow_shell,max_cells=MAX_FILLED-used)
        else:
            volume=mesh.voxelized(pitch)
            if mesh.is_watertight:volume=volume.fill()
            cellpoints=np.asarray(volume.points,dtype=float)
        if used+len(cellpoints)>MAX_FILLED:
            raise ValueError('Filled voxel safety limit reached; lower --xy/--z')
        used+=len(cellpoints)
        if not len(cellpoints):continue
        indices=np.rint((cellpoints-origin)/pitch).astype(int)
        indices=np.clip(indices,0,shape-1)
        if manifold=='union':
            # CSG geometry is new topology; restore RGBA from *original* UVs.
            best=np.full(len(cellpoints),np.inf,dtype=np.float64)
            colors=np.zeros((len(cellpoints),4),dtype=np.uint8)
            for original,spec in zip(meshes,specs):
                candidate,d2=colors_at(original,cellpoints,spec,with_distance=True)
                closer=d2<best
                colors[closer]=candidate[closer]
                best[closer]=d2[closer]
        else:
            colors=colors_at(meshes[index],cellpoints,specs[index])
        grid[indices[:,2],indices[:,1],indices[:,0]]=colors
    if not np.any(grid[:,:,:,3]>=128):
        raise ValueError('No opaque samples, cannot produce original sprite stacking')
    out.mkdir(parents=True,exist_ok=True)
    folder=out/'layers';folder.mkdir()
    layers=[]
    for i in range(grid.shape[0]):
        name=f'layers/{i:03d}.png'
        Image.fromarray(grid[i][::-1].copy(),'RGBA').save(out/name,optimize=True)
        layers.append(name)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    metadata={'format':'sprite-stacking-grunge/1','source_sha256':digest,'source_glb':str(source),
      'layers':layers,'spacing':[pitch,pitch,pitch],
      'pivot':[float(v) for v in origin+pitch*(shape-1)*0.5],
      'size':384,'axes':'X-right Y-forward Z-up; layer zero at bottom',
      'note':'Original surface colors on occupied voxel centers; spatial approximation only.',
      'aabb':[lower.tolist(),upper.tolist()],'voxel_grid':list(map(int,shape)),
      'occupied':int((grid[:,:,:,3]>=128).sum()),'mesh_count':len(meshes),
      'shell_mode':bool(allow_shell),'voxelizer':backend,'manifold':manifold_meta,'not_gameplay':True}
    (out/'stack.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
    return metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--xy',type=int,default=192)
    p.add_argument('--z',type=int,default=96)
    p.add_argument('--allow-shell',action='store_true',help='Use existing open surfaces as thin shells, not invented interior')
    p.add_argument('--manifold',choices=['off','audit','normalize','union'],default='audit',
                   help='Manifold3D: optional audit by default; normalize/union only when explicitly requested')
    p.add_argument('--voxelizer',choices=['auto','open3d','trimesh'],default='auto',
                   help='Prefer Open3D if installed, preserve existing trimesh fallback')
    a=p.parse_args()
    if not 16<=a.xy<=384 or not 8<=a.z<=192:p.error('Grid limits: xy=16..384, z=8..192')
    s=convert(a.source,a.out,a.xy,a.z,a.allow_shell,a.voxelizer,a.manifold)
    print(f'STACK: {len(s["layers"])} layers, {s["occupied"]} voxels via {s["voxelizer"]}; GLB SHA-256 {s["source_sha256"]}')

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError,ImportError) as error:sys.exit('ERROR: '+str(error))
