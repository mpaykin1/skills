#!/usr/bin/env python3
"""Apache-2.0 Manifold3D adapter for real original-GLB sprite stacking.

Uses official manifold3d.Mesh/Manifold Python bindings; optional native module.
NEVER reassigns source UVs/vertex art. Geometry candidates are ONLY used to
compute voxel occupancy. Colors always come from original source triangles.

Manifold cannot magically fix arbitrary open or intersecting meshes. Union is
opt-in and only allowed for static, closed, verified solids. Keep node-level
animation/door/wheel components separate in the upstream scene-parts bridge.
"""
from __future__ import annotations
import numpy as np
import trimesh

MAX_UNION_PARTS = 8
MAX_FACES = 400_000


def available() -> bool:
    try:
        import manifold3d  # noqa: F401
        return True
    except ImportError:
        return False


def _checked_model(mesh: trimesh.Trimesh):
    import manifold3d as m3d
    topology = mesh.copy()  # NEVER change the original UV/vertex colors.
    # Merged positions needed for texture-seam-split GLB vertices. No UV change
    # is used for coloring; the original mesh is kept by the caller.
    topology.merge_vertices(merge_tex=True, merge_norm=True)
    if (not topology.is_watertight or not topology.is_winding_consistent
            or not len(topology.faces)):
        raise ValueError('Mesh is open/nonmanifold or winding-inconsistent after UV-seam welding; do not cap holes')
    vertices = np.asarray(topology.vertices, dtype=np.float64)
    faces = np.asarray(topology.faces, dtype=np.int64)
    if (len(faces) > MAX_FACES or not np.isfinite(vertices).all()
            or faces.min() < 0 or faces.max() >= len(vertices)
            or len(vertices) > np.iinfo(np.uint32).max):
        raise ValueError('Unsafe original mesh for Manifold3D')
    # Float32 is the documented official manifold3d.Mesh format.
    native = m3d.Manifold(m3d.Mesh(
        vert_properties=np.ascontiguousarray(vertices, dtype=np.float32),
        tri_verts=np.ascontiguousarray(faces, dtype=np.uint32)))
    if native.is_empty():
        raise ValueError('Manifold3D rejected mesh topology (empty result)')
    if float(native.volume()) <= 0:
        raise ValueError('Manifold3D returned nonpositive closed volume')
    return native, topology


def _to_trimesh(native):
    out = native.to_mesh()
    result = trimesh.Trimesh(
        vertices=np.asarray(out.vert_properties, dtype=np.float64)[:, :3].copy(),
        faces=np.asarray(out.tri_verts, dtype=np.int64).copy(), process=False)
    if (not result.is_watertight or not result.is_winding_consistent
            or not len(result.faces) or not np.isfinite(result.vertices).all()):
        raise ValueError('Invalid Manifold3D output; keep original GLB')
    return result


def _same_envelope(source:trimesh.Trimesh, derived:trimesh.Trimesh, *, bound_tol=1e-4):
    original_bounds=np.asarray(source.bounds, dtype=np.float64)
    new_bounds=np.asarray(derived.bounds, dtype=np.float64)
    diagonal=float(np.linalg.norm(original_bounds[1]-original_bounds[0]))
    maxerr=max(1e-5, diagonal*bound_tol)
    if not np.allclose(original_bounds,new_bounds,rtol=0,atol=maxerr):
        raise ValueError('Manifold3D changed original object bounding box; rejecting')


def prepare(meshes, mode: str):
    """Return (occupancy_meshes, status). Materials belong to ORIGINAL meshes.

    `audit`: check each closed input if installed, never replace geometry.
    `normalize`: request topology-normalized candidate per closed source mesh.
    `union`: CSG union of <=8 closed, static meshes. Only explicit request.
    `off`: keep previous pipeline byte-for-byte as a voxelization choice.
    """
    if mode not in ('off','audit','normalize','union'):
        raise ValueError('manifold mode must be off/audit/normalize/union')
    if mode=='off':return meshes, {'mode':'off','used':False}
    if not available():
        if mode=='audit':return meshes, {'mode':'audit','used':False,'reason':'manifold3d not installed'}
        raise RuntimeError('manifold3d native module missing; install `manifold3d` or use --manifold audit/off')
    if mode=='union' and (len(meshes)<2 or len(meshes)>MAX_UNION_PARTS):
        raise ValueError('CSG union explicitly requires 2..8 independent static closed meshes')
    results=[]; normals=[]; issues=[]
    for idx,mesh in enumerate(meshes):
        try:
            native,topology=_checked_model(mesh)
            if mode!='audit':
                candidate=_to_trimesh(native)
                _same_envelope(topology,candidate)
                old_vol=abs(float(topology.volume)); new_vol=abs(float(candidate.volume))
                if (old_vol<=0 or abs(new_vol-old_vol)/old_vol>0.02):
                    raise ValueError('Manifold3D changed object volume over 2%')
                results.append(candidate)
            normals.append(native)
        except (ValueError,RuntimeError) as exc:
            if mode!='audit':raise ValueError(f'Manifold3D cannot safely prepare mesh #{idx}: {exc}') from exc
            issues.append(f'mesh #{idx}: {exc}')
    if mode=='audit':
        return meshes, {'mode':'audit','used':False,'inspected':len(meshes),'valid':len(normals),'issues':issues[:8]}
    if mode=='normalize':
        return results, {'mode':'normalize','used':True,'meshes':len(results),'colors_from':'original meshes'}
    # Genuine CSG union. Preserve source bounds and enforce approximate volume
    # envelope. Changes to internal touching surfaces are allowed only here.
    import manifold3d as m3d
    native_union=m3d.Manifold.batch_boolean(normals,m3d.OpType.Add)
    if native_union.is_empty():raise ValueError('CSG union returned empty solid')
    combined=_to_trimesh(native_union)
    original_min=np.min([mesh.bounds[0] for mesh in meshes],axis=0)
    original_max=np.max([mesh.bounds[1] for mesh in meshes],axis=0)
    extent=max(1e-5,float(np.linalg.norm(original_max-original_min))*1e-4)
    if (np.max(np.abs(combined.bounds[0]-original_min))>extent
            or np.max(np.abs(combined.bounds[1]-original_max))>extent):
        raise ValueError('CSG union shifted original silhouettes')
    volumes=[abs(float(x.volume)) for x in results]
    union_volume=abs(float(combined.volume))
    if union_volume>sum(volumes)*1.005 or union_volume<max(volumes)*0.995:
        raise ValueError('CSG union produced implausible occupancy volume')
    if len(combined.faces)>MAX_FACES:
        raise ValueError('CSG union topology exceeds safe triangle budget')
    return [combined], {'mode':'union','used':True,'meshes':len(meshes),
                        'volume':union_volume,'colors_from':'original source triangles',
                        'note':'Boolean topology changes may alter visual silhouettes; verify Playwright/Pixelmatch'}
