#!/usr/bin/env python3
"""CPU-only: real volumetric RGBA slices from original triangle meshes/posed OBJs.

Uses trimesh voxelization, scipy nearest-surface matching and Pillow. No fake
extrusion of a flat picture, no NVIDIA/CUDA, no topology changes to source.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def load_geometry(path: Path):
    import trimesh
    scene = trimesh.load_scene(str(path), process=False)
    records = []
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        mesh = scene.geometry[geometry].copy()
        mesh.apply_transform(transform)
        if len(mesh.faces) and len(mesh.vertices):
            records.append((str(node), mesh))
    if not records:
        raise ValueError(f'No triangle mesh found: {path}')
    return records


def prepare_color(mesh):
    """Original material colors/textures, not freshly invented grunge patterns."""
    import numpy as np
    vis=mesh.visual
    face_count=len(mesh.faces)
    result={'face':np.broadcast_to(np.array([115,106,95,255],dtype=np.uint8),(face_count,4)).copy()}
    if vis.kind=='vertex':
        colors=np.asarray(vis.vertex_colors,dtype=np.uint8)
        if len(colors)==len(mesh.vertices):
            result['face']=colors[np.asarray(mesh.faces,dtype=int)].mean(axis=1).astype(np.uint8)
    elif vis.kind=='face':
        colors=np.asarray(vis.face_colors,dtype=np.uint8)
        if len(colors)==face_count:result['face']=colors.copy()
    elif vis.kind=='texture':
        mat=getattr(vis,'material',None)
        base=getattr(mat,'baseColorFactor',None)
        if base is not None and len(base)>=3:
            factor=np.asarray(base[:4],dtype=float)
            if len(factor)==3: factor=np.append(factor,255.)
            if float(factor.max())<=1.0:factor=factor*255.0
            result['face'][:]=np.clip(factor,0,255).astype(np.uint8)
        else:
            diffuse=getattr(mat,'diffuse',None)
            if diffuse is not None and len(diffuse)>=3:
                result['face'][:]=np.asarray(diffuse,dtype=np.uint8)[:4]
        tex=getattr(mat,'baseColorTexture',None)
        if tex is None:tex=getattr(mat,'image',None)
        uv=getattr(vis,'uv',None)
        if tex is not None and uv is not None and len(uv)==len(mesh.vertices):
            from PIL import Image
            try:
                texture=np.asarray(Image.fromarray(tex).convert('RGBA') if not hasattr(tex,'convert') else tex.convert('RGBA'))
                result['texture']=texture
                result['uv']=np.asarray(uv,dtype=np.float64)
            except (TypeError,ValueError):pass
    return result


def surface_rgba(mesh, query, mat, limit=32768):
    """Color by nearest triangle/UV, retaining source material orientation.
    The centroid nearest-triangle heuristic is not a substitute for an exact
    ray/triangle material baker on very long or highly irregular triangles.
    """
    import numpy as np
    from scipy.spatial import cKDTree
    faces=mesh.faces
    tri=np.asarray(mesh.vertices)[faces]
    tree=cKDTree(tri.mean(axis=1))
    out=np.zeros((len(query),4),np.uint8)
    uv=mat.get('uv')
    tex=mat.get('texture')
    for start in range(0,len(query),limit):
        sl=slice(start,min(start+limit,len(query)))
        xyz=query[sl]
        _, ix=tree.query(xyz, workers=1)
        col=mat['face'][ix].copy()
        if uv is not None and tex is not None:
            tri_xyz=tri[ix]
            a,b,c=tri_xyz[:,0,:],tri_xyz[:,1,:],tri_xyz[:,2,:]
            v0,v1,v2=b-a,c-a,xyz-a
            d00=np.einsum('ij,ij->i',v0,v0);d01=np.einsum('ij,ij->i',v0,v1)
            d11=np.einsum('ij,ij->i',v1,v1);d20=np.einsum('ij,ij->i',v2,v0);d21=np.einsum('ij,ij->i',v2,v1)
            denom=d00*d11-d01*d01
            valid=np.abs(denom)>1e-15
            u=np.zeros(len(xyz));v=np.zeros(len(xyz));
            u[valid]=(d11[valid]*d20[valid]-d01[valid]*d21[valid])/denom[valid]
            v[valid]=(d00[valid]*d21[valid]-d01[valid]*d20[valid])/denom[valid]
            u=np.clip(u,0,1);v=np.clip(v,0,1)
            w=np.clip(1-u-v,0,1)
            xy_uv=uv[faces[ix]]
            uv_interpolated=xy_uv[:,0]*w[:,None]+xy_uv[:,1]*u[:,None]+xy_uv[:,2]*v[:,None]
            h,ww=tex.shape[:2]
            tx=np.mod(np.round(uv_interpolated[:,0]*(ww-1)).astype(int),ww)
            ty=np.mod(np.round((1-uv_interpolated[:,1])*(h-1)).astype(int),h)
            texcolor=tex[ty,tx]
            col=(texcolor.astype(float)*col.astype(float)/255.0).round().astype(np.uint8)
        # Sprite-stacked solid occupies the raymarch cell; alpha is binary.
        col[:,3]=255
        out[sl]=col
    return out


def build_volume(records, dimensions, spacing, pivot, *, allow_open=False):
    import numpy as np
    nx,ny,nz=dimensions
    dx,dy,dz=spacing
    grid=np.zeros((nz,ny,nx,4),np.uint8)
    # All frames share the same grid bounds, coordinates and pivot.
    coords=np.indices((nz,ny,nx),dtype=float)
    points=np.empty((nz*ny*nx,3),dtype=np.float64)
    points[:,0]=((coords[2].ravel()+.5-nx/2)*dx+pivot[0])
    points[:,1]=((coords[1].ravel()+.5-ny/2)*dy+pivot[1])
    points[:,2]=((coords[0].ravel()+.5-nz/2)*dz+pivot[2])
    flat=grid.reshape(-1,4)
    counts=[]
    for name, mesh in records:
        if not mesh.is_watertight and not allow_open:
            raise ValueError(f'Open non-watertight surface {name}: cannot invent its interior; repair with PyMeshLab or pass --allow-open')
        # Capped world-space grid, no silent gigantic intermediate arrays.
        pitch=min(spacing)
        bounds=np.asarray(mesh.bounds)
        implied=np.ceil((bounds[1]-bounds[0])/pitch+4).astype(int)
        if int(np.prod(implied))>14_000_000:
            raise ValueError(f'{name} would need {int(np.prod(implied)):,} temporary cells; lower --xy-size or --z-slices')
        vox=mesh.voxelized(pitch=pitch)
        if mesh.is_watertight: vox=vox.fill()
        vmat=vox.matrix
        # Real point-occupancy from original geometry, not silhouette extrusion.
        idx=np.rint((points-vox.transform[:3,3])/pitch).astype(int)
        ok=((idx>=0)&(idx<np.array(vmat.shape))).all(axis=1)
        candidates=np.flatnonzero(ok & (flat[:,3]==0))
        if len(candidates):
            ii=idx[candidates]
            hit=candidates[vmat[ii[:,0],ii[:,1],ii[:,2]]]
            if len(hit):flat[hit]=surface_rgba(mesh,points[hit],prepare_color(mesh))
        counts.append({'name':name,'vertices':int(len(mesh.vertices)),'faces':int(len(mesh.faces)),
                       'watertight':bool(mesh.is_watertight)})
    if not (flat[:,3]>0).any():raise ValueError('No occupied volume cells; increase resolution or examine source')
    return grid,counts


def compute_grid(frames, xy_size, z_slices):
    import numpy as np
    all_bounds=np.stack([np.asarray(mesh.bounds) for meshes in frames for _,mesh in meshes])
    lo=all_bounds[:,0].min(axis=0);hi=all_bounds[:,1].max(axis=0)
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():raise ValueError('Geometry contains nonfinite coordinates')
    span=hi-lo
    if np.max(span)<1e-6:raise ValueError('Zero-sized geometry')
    lateral=max(span[0],span[1],1e-3)
    xy_pitch=lateral/max(4,xy_size-4)
    z_pitch=max(span[2],1e-3)/max(4,z_slices-4)
    pivot=((lo+hi)*.5).tolist()
    return [xy_size,xy_size,z_slices],[xy_pitch,xy_pitch,z_pitch],pivot


def save_stack(folder, volume, dims, spacing, pivot, metadata, label):
    import numpy as np
    from PIL import Image
    folder.mkdir(parents=True,exist_ok=False)
    layerdir=folder/'layers';layerdir.mkdir()
    nx,ny,nz=dims
    pngs=[]
    atlas_cols=math.ceil(math.sqrt(nz));atlas_rows=math.ceil(nz/atlas_cols)
    atlas=Image.new('RGBA',(nx*atlas_cols,ny*atlas_rows))
    for z in range(nz):
        # PNGs are top-row +Y, Data3DTexture is y-positive from row 0.
        im=Image.fromarray(np.ascontiguousarray(volume[z,::-1]),'RGBA')
        name=f'layers/{z:03d}.png';im.save(folder/name,optimize=True)
        pngs.append(name)
        atlas.paste(im,((z%atlas_cols)*nx,(z//atlas_cols)*ny))
    atlas.save(folder/'stack.atlas.png',optimize=True)
    meta={'format':'monster-sprite-stack-v2','axes':'+X-right,+Y-top-of-png,+Z-up',
          'layers':pngs,'atlas':'stack.atlas.png','atlasCols':atlas_cols,'atlasRows':atlas_rows,
          'spacing':spacing,'pivot':pivot,'size':nx,'dimensions':dims,
          'source_label':label,'source_kind':'original triangle geometry, CPU voxelized',
          'objects':metadata,'alpha':'binary occupied-volume cells',
          'volume_sha256':hashlib.sha256(volume.tobytes()).hexdigest()}
    (folder/'stack.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    return meta


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--input',help='Source GLB, OBJ or PLY (geometry, not a flat image)')
    source.add_argument('--frames-dir',help='Numbered OBJ frame meshes exported from real Blender poses')
    p.add_argument('--output',required=True)
    p.add_argument('--xy-size',type=int,choices=(64,96,128,192,256),default=128)
    p.add_argument('--z-slices',type=int,choices=(32,48,64,96,128),default=96)
    p.add_argument('--fps',type=int,default=12)
    p.add_argument('--shared-grid',help='JSON dimensions/spacing/pivot common to ALL monster action clips')
    p.add_argument('--clip',default='IDLE_BREATH')
    p.add_argument('--allow-open',action='store_true',help='Explicitly use thin-surface voxelization for open meshes')
    p.add_argument('--orbit-gif',action='store_true')
    args=p.parse_args(argv)
    out=Path(args.output).expanduser().resolve()
    if out.exists():p.error('Output already exists; choose another destination (approved assets never overwritten)')
    if not 1<=args.fps<=60:p.error('FPS must be 1..60')
    if args.input:
        files=[Path(args.input).expanduser().resolve()]
    else:
        folder=Path(args.frames_dir).expanduser().resolve()
        files=sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in ('.obj','.glb','.ply'))
        if not files:p.error('No geometry frames in --frames-dir')
    for f in files:
        if not f.is_file():p.error(f'Missing source mesh {f}')
    frames=[load_geometry(f) for f in files]
    if args.shared_grid:
        ref=json.loads(Path(args.shared_grid).resolve().read_text(encoding='utf8'))
        dims,spacing,pivot=ref['dimensions'],ref['spacing'],ref['pivot']
        if dims[0]!=args.xy_size or dims[1]!=args.xy_size or dims[2]!=args.z_slices:
            raise ValueError('Shared animation-grid dimensions differ from requested resolution')
        import numpy as np
        for records in frames:
            for name,mesh in records:
                mn,mx=np.asarray(mesh.bounds)
                grid_lo=np.asarray(pivot)-np.asarray(dims)*np.asarray(spacing)*0.5
                grid_hi=np.asarray(pivot)+np.asarray(dims)*np.asarray(spacing)*0.5
                if np.any(mn<grid_lo) or np.any(mx>grid_hi):
                    raise ValueError('Mesh exceeds shared volume bounds: '+name)
    else:
        dims,spacing,pivot=compute_grid(frames,args.xy_size,args.z_slices)
    out.mkdir(parents=True)
    items=[]
    for k, (f,records) in enumerate(zip(files,frames)):
        vol,objects=build_volume(records,dims,spacing,pivot,allow_open=args.allow_open)
        sub=f'pose_{k:03d}'
        meta=save_stack(out/sub,vol,dims,spacing,pivot,objects,f.stem)
        items.append({'path':sub+'/stack.json','atlas':sub+'/stack.atlas.png','label':f.stem,'cells':int((vol[...,3]>0).sum())})
        print('[sprite stacking]',sub,'filled cells:',items[-1]['cells'])
    mainmeta={'format':'monster-sprite-stack-clip-v2','version':'2.0.0','clip':args.clip,
              'fps':args.fps,'frames':items,'dimensions':dims,'spacing':spacing,'pivot':pivot,
              'animation':'independent geometry-baked full stack per sampled pose',
              'runtime':'runtime/sprite_stack_three.js'}
    (out/'clip.json').write_text(json.dumps(mainmeta,indent=2),encoding='utf8')
    if args.orbit_gif:
        import subprocess
        cmd=[sys.executable,str(Path(__file__).with_name('render_sprite_stack.py')),
             str(out/'pose_000'/'stack.json'),str(out/'preview'), '--frames','36']
        subprocess.run(cmd,check=True)
    print('[sprite stacking] ready',out,'frames:',len(items),'dimensions:',dims)

if __name__=='__main__':main()
