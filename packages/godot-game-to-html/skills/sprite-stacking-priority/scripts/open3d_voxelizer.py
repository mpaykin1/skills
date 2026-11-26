#!/usr/bin/env python3
"""Open3D CPU raycasting occupancy/surface-distance voxel source adapter.

Inputs are actual WORLD-TRANSFORMED trimesh triangles from the existing GLB
pipeline. For watertight meshes occupancy uses odd-ray hit tests; the narrow
surface band preserves visible exterior cells. Open surfaces get ONLY a thin
band around existing faces (no invented filled interior).
"""
from __future__ import annotations
import numpy as np

# Safety budgets are mirrored by stack_from_glb.py; do not materialize full 3D grids
# as Open3D query point arrays in one shot.
MAX_BATCH = 65536


def available() -> bool:
    try:
        import open3d  # noqa: F401
    except ImportError:
        return False
    return True


def voxel_points(mesh, origin, pitch, shape, allow_shell=True, max_cells=1_000_000):
    """Return actual voxel-center XYZ positions near original triangles.

    Does NOT infer closed volume for nonwatertight mesh. Preserves original
    holes at the source grid's resolution. Colors are sampled by the caller
    exclusively from original mesh UV/vertex/face colors.
    """
    try:
        import open3d as o3d
    except ImportError as err:
        raise RuntimeError('Open3D Python package missing. Install open3d or use --voxelizer trimesh') from err
    if not mesh.is_watertight and not allow_shell:
        raise ValueError('Open surface cannot be filled: use --allow-shell or original GLB')
    vertices=np.asarray(mesh.vertices, dtype=np.float32)
    triangles=np.asarray(mesh.faces, dtype=np.uint32)
    if len(vertices)==0 or len(triangles)==0 or not np.isfinite(vertices).all():
        raise ValueError('Invalid original mesh triangles for Open3D')
    ray=o3d.t.geometry.RaycastingScene()
    ray.add_triangles(o3d.core.Tensor(vertices,dtype=o3d.core.Dtype.Float32),
                      o3d.core.Tensor(triangles,dtype=o3d.core.Dtype.UInt32))
    origin=np.asarray(origin,dtype=np.float64)
    shape=np.asarray(shape,dtype=np.int64)
    vmin=vertices.min(axis=0).astype(np.float64)
    vmax=vertices.max(axis=0).astype(np.float64)
    # Index ranges include outer cells within a half-diagonal surface band.
    lo=np.maximum(0,np.floor((vmin-origin)/pitch-1.5).astype(np.int64))
    hi=np.minimum(shape,np.ceil((vmax-origin)/pitch+2.5).astype(np.int64))
    if np.any(hi<=lo):return np.empty((0,3),dtype=np.float64)
    xcount=int(hi[0]-lo[0]);ycount=int(hi[1]-lo[1]);zcount=int(hi[2]-lo[2])
    total=xcount*ycount*zcount
    filled=[]; count=0
    shell_width=0.51*float(pitch)
    for offset in range(0,total,MAX_BATCH):
        # XYZ index generation uses x as the innermost axis. No large meshgrid.
        linear=np.arange(offset,min(total,offset+MAX_BATCH),dtype=np.int64)
        xx=lo[0]+linear%xcount
        yy=lo[1]+(linear//xcount)%ycount
        zz=lo[2]+linear//(xcount*ycount)
        indices=np.stack((xx,yy,zz),axis=1)
        centers=(origin+indices*float(pitch)).astype(np.float32)
        query=o3d.core.Tensor(centers,dtype=o3d.core.Dtype.Float32)
        dist=np.asarray(ray.compute_distance(query).numpy()).reshape(-1)
        # For open triangles, occupancy would make invalid inside/outside claims.
        mask=dist<=shell_width
        if mesh.is_watertight:
            inside=np.asarray(ray.compute_occupancy(query,nsamples=3).numpy()).reshape(-1)>.5
            mask|=inside
        if not np.isfinite(dist).all():
            raise RuntimeError('Open3D returned non-finite distance; preserving original GLB')
        if np.any(mask):
            subset=centers[mask].astype(np.float64)
            count+=len(subset)
            if count>max_cells:raise ValueError('Open3D voxel limit exceeded; reduce --xy/--z')
            filled.append(subset)
    if not filled:return np.empty((0,3),dtype=np.float64)
    return np.concatenate(filled,axis=0)
