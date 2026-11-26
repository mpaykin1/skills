#!/usr/bin/env python3
"""CPU-only Trimesh structural analysis for Monster Anatomy 3D GLB assets.

Read-only. Inspects rest-pose triangle geometry without removing or creating
vertices, re-binding bones or editing animated clips / morph targets.

Requires the real open-source trimesh + numpy, installed in this interpreter.
This is not a substitute for Khronos glTF-Validator or playback in Three.js.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True,help='Existing uncompressed .glb')
    p.add_argument('--strict',action='store_true',help='Fail on degenerate/nonmanifold triangles or inconsistent winding')
    p.add_argument('--max-meshes',type=int,default=10000,help='Refuse unexpected geometry explosion')
    return p.parse_args(argv)


def glb_metadata(path):
    # Use our preexisting, validated GLB-header and JSON parser.
    from gltf_transform_worker import read_glb
    doc=read_glb(path)
    required=set(doc.get('extensionsRequired',[]))|set(doc.get('extensionsUsed',[]))
    if 'EXT_meshopt_compression' in required or 'KHR_meshopt_compression' in required:
        raise ValueError('Trimesh CPU mesh audit requires an UNCOMPRESSED GLB; run audit before meshopt compression')
    if 'KHR_draco_mesh_compression' in required:
        raise ValueError('Draco-compressed mesh requires decoder; run Trimesh audit before compression')
    return doc


def inspect_mesh(name, mesh):
    import numpy as np
    import trimesh
    vertices=np.asarray(mesh.vertices)
    faces=np.asarray(mesh.faces)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or faces.ndim!=2 or faces.shape[1]!=3:
        raise ValueError(f'{name}: expected triangular 3D mesh')
    if len(vertices)<3 or len(faces)<1:
        raise ValueError(f'{name}: empty geometry')
    if not np.isfinite(vertices).all():
        raise ValueError(f'{name}: nonfinite mesh vertices')
    if (faces<0).any() or (faces>=len(vertices)).any():
        raise ValueError(f'{name}: out-of-bounds triangle index')
    bounds=np.asarray(mesh.bounds)
    extent=float(np.max(bounds[1]-bounds[0]))
    if not math.isfinite(extent) or extent<=0:
        raise ValueError(f'{name}: invalid 3D bounds')
    # Relative area threshold is scale-independent. Very thin real muscle
    # panels are allowed; only numerically collapsed faces are flagged.
    threshold=max(extent*extent*1e-14,1e-25)
    areas=np.asarray(mesh.area_faces)
    if not np.isfinite(areas).all():
        raise ValueError(f'{name}: invalid triangle areas')
    degenerate=int(np.count_nonzero(areas<=threshold))
    # Count triangle occurrences per undirected edge. A boundary is allowed
    # for intentionally open skin and single-sided tendons; >2 is non-manifold.
    edges=np.asarray(mesh.edges_sorted)
    _edges, counts=np.unique(edges,axis=0,return_counts=True)
    boundaries=int(np.count_nonzero(counts==1))
    nonmanifold=int(np.count_nonzero(counts>2))
    # trimesh checks topology without rewriting source geometry or GLB.
    watertight=bool(mesh.is_watertight)
    winding=bool(mesh.is_winding_consistent)
    # Avoid computing expensive expensive convex hulls/signed distances.
    out={
      'name':str(name),
      'vertices':int(len(vertices)),
      'triangles':int(len(faces)),
      'degenerate_triangles':degenerate,
      'boundary_edges':boundaries,
      'nonmanifold_edges':nonmanifold,
      'watertight':watertight,
      'consistent_winding':winding,
      'bounds':[round(float(x),6) for x in np.ravel(bounds)],
    }
    return out


def inspect_glb(source:Path, strict:bool=False,max_meshes:int=10000):
    import trimesh
    if max_meshes<=0:raise ValueError('--max-meshes must be positive')
    doc=glb_metadata(source)
    scene=trimesh.load(str(source),force='scene',process=False)
    geometries=list(scene.geometry.items())
    if not geometries:raise ValueError('Trimesh found zero triangle meshes')
    if len(geometries)>max_meshes:raise ValueError(f'Too many mesh records ({len(geometries)})')
    # Geometry can have multiple instances and scene graph transforms;
    # Trimesh reports unique geometry, not a bone-deformed animation pose.
    stats=[]
    for name,mesh in geometries:
        if not isinstance(mesh,trimesh.Trimesh):
            continue # e.g. line/point geometry is not a triangle surface
        stats.append(inspect_mesh(name,mesh))
    if not stats:raise ValueError('No triangle mesh surfaces to analyze')
    errors=[];warnings=[]
    for item in stats:
        if item['degenerate_triangles']:
            errors.append(f"{item['name']}: {item['degenerate_triangles']} collapsed triangles")
        if item['nonmanifold_edges']:
            warnings.append(f"{item['name']}: {item['nonmanifold_edges']} edges shared by >2 triangles")
        if item['boundary_edges']:
            warnings.append(f"{item['name']}: {item['boundary_edges']} open boundary edges (may be intentional)")
        if not item['consistent_winding']:
            warnings.append(f"{item['name']}: inconsistent triangle winding")
    if strict:
        errors.extend(w for w in warnings if 'shared by >2' in w or 'inconsistent triangle winding' in w)
    result={
      'trimesh_version':trimesh.__version__,
      'mesh_records':len(stats),
      'vertices':sum(x['vertices'] for x in stats),
      'triangles':sum(x['triangles'] for x in stats),
      'skins_in_glb':len(doc.get('skins',[])),
      'animations_in_glb':len(doc.get('animations',[])),
      'morph_primitives_in_glb':sum(bool(p.get('targets')) for m in doc.get('meshes',[]) for p in m.get('primitives',[])),
      'errors':errors,
      'warnings':warnings,
    }
    return result


def main(argv=None):
    args=parse_args(argv)
    path=args.input.expanduser().resolve()
    if not path.is_file() or path.suffix.lower()!='.glb':
        raise ValueError('Input must be a local .glb file')
    # No write operations whatsoever. SHA check also catches accidental
    # operations in future changes to upstream loader or our implementation.
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    result=inspect_glb(path,strict=args.strict,max_meshes=args.max_meshes)
    after=hashlib.sha256(path.read_bytes()).hexdigest()
    if before!=after:raise RuntimeError('Read-only audit modified input GLB (unexpected)')
    print('[Trimesh CPU] mesh={mesh_records} vertex={vertices} triangle={triangles} '
          'skins={skins_in_glb} clips={animations_in_glb} morph_parts={morph_primitives_in_glb}'
          .format(**result))
    for issue in result['warnings'][:20]:print('[Trimesh CPU] WARNING:',issue)
    for issue in result['errors'][:20]:print('[Trimesh CPU] ERROR:',issue,file=sys.stderr)
    if len(result['warnings'])>20:print('[Trimesh CPU] Additional warnings:',len(result['warnings'])-20)
    if len(result['errors'])>20:print('[Trimesh CPU] Additional errors:',len(result['errors'])-20,file=sys.stderr)
    if result['errors']:raise RuntimeError('Trimesh rejected unsafe geometry; original GLB remains unchanged')
    print('[Trimesh CPU] Geometry audit complete (no source modification)')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ImportError,OSError,ValueError,RuntimeError) as e:
        print('[Trimesh CPU] BLOCKED:',e,file=sys.stderr)
        raise SystemExit(2)
