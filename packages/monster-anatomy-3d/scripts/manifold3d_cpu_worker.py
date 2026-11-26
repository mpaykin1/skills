#!/usr/bin/env python3
"""CPU-only Manifold3D Boolean union of read-only rest-geometry mesh snapshots.

The JSON bridge preserves an approved Blender character by creating a separate
non-exportable sculpt reference from snapshots (can be taken from a rigged hero).
Never transfers source UV, weights, morphs or materials into different topology.
Requires real official manifold3d; no fallbacks that imitate the algorithm.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile

MAX_MESHES = 24
MAX_VERTICES = 160_000
MAX_TRIANGLES = 300_000


def process(data: dict) -> dict:
    import numpy as np
    import trimesh
    try:
        from manifold3d import Manifold, Mesh, OpType, Error
    except ImportError as exc:
        raise RuntimeError('Real manifold3d is absent: pip install manifold3d==3.5.5. CPU-only; no fake Boolean fallback.') from exc

    incoming = data.get('meshes')
    if not isinstance(incoming, list) or not 2 <= len(incoming) <= MAX_MESHES:
        raise ValueError('Supply 2..24 closed solid mesh snapshots')
    bodies = []
    bounds = []
    points = 0
    faces_total = 0
    source_names = set()
    for item in incoming:
        if not isinstance(item, dict):
            raise ValueError('Mesh record must be an object')
        name = item.get('name')
        if not isinstance(name, str) or not name.strip() or name in source_names:
            raise ValueError('Unique nonempty object names required')
        source_names.add(name)
        vertices = np.asarray(item.get('vertices'), dtype=np.float64)
        triangles = np.asarray(item.get('faces'), dtype=np.int64)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 4:
            raise ValueError(f'{name}: must have Nx3 vertices (N>=4)')
        if triangles.ndim != 2 or triangles.shape[1] != 3 or len(triangles) < 4:
            raise ValueError(f'{name}: must have Mx3 triangles (M>=4)')
        points += len(vertices)
        faces_total += len(triangles)
        if points > MAX_VERTICES or faces_total > MAX_TRIANGLES:
            raise ValueError('Geometry exceeds CPU safety limit')
        if not np.isfinite(vertices).all():
            raise ValueError(f'{name}: nonfinite vertex')
        if triangles.min() < 0 or triangles.max() >= len(vertices):
            raise ValueError(f'{name}: invalid face indices')
        if np.any(triangles[:, 0] == triangles[:, 1]) or np.any(triangles[:, 1] == triangles[:, 2]) or np.any(triangles[:, 0] == triangles[:, 2]):
            raise ValueError(f'{name}: duplicate face indices')
        tri = trimesh.Trimesh(vertices=vertices, faces=triangles, process=False, validate=False)
        if not (tri.is_watertight and tri.is_winding_consistent and tri.is_volume):
            raise ValueError(f'{name}: mesh must be closed, consistently wound, and positive-volume; repair with PyMeshLab first')
        # Triangles with zero area are not safe for CSG, even on a topologically closed shell.
        if len(tri.area_faces) != len(triangles) or float(np.min(tri.area_faces)) <= 1e-14:
            raise ValueError(f'{name}: degenerate triangle')
        candidate = Manifold(Mesh(vert_properties=vertices.astype(np.float32),
                                  tri_verts=triangles.astype(np.uint32)))
        if candidate.status() != Error.NoError or candidate.is_empty():
            raise ValueError(f'{name}: Manifold3D could not ingest mesh: {candidate.status()}')
        bodies.append(candidate)
        bounds.append(np.asarray(tri.bounds, dtype=np.float64))
    union = Manifold.batch_boolean(bodies, OpType.Add)
    if union.status() != Error.NoError or union.is_empty():
        raise ValueError(f'Manifold union failed: {union.status()}')
    result = union.to_mesh()
    out_vertices = np.asarray(result.vert_properties, dtype=np.float64)[:, :3]
    out_triangles = np.asarray(result.tri_verts, dtype=np.int64)
    if not (4 <= len(out_vertices) <= MAX_VERTICES * 8 and 4 <= len(out_triangles) <= MAX_TRIANGLES * 8):
        raise ValueError('Union size outside safe limits')
    if not np.isfinite(out_vertices).all():
        raise ValueError('Union has nonfinite vertices')
    tri_union = trimesh.Trimesh(vertices=out_vertices, faces=out_triangles, process=False)
    if not (tri_union.is_watertight and tri_union.is_winding_consistent and tri_union.is_volume):
        raise ValueError('Union failed independent Trimesh solid topology check')
    input_min = np.min([a[0] for a in bounds], axis=0)
    input_max = np.max([a[1] for a in bounds], axis=0)
    tolerance = max(1e-5, float(np.max(input_max-input_min)) * 1e-4)
    if max(float(np.max(np.abs(tri_union.bounds[0]-input_min))),float(np.max(np.abs(tri_union.bounds[1]-input_max)))) > tolerance:
        raise ValueError('CSG changed the overall bounds; refusing candidate')
    return {
        'format': 'manifold-sculpt-guide-v1',
        'source_objects': sorted(source_names),
        'vertices': out_vertices.tolist(),
        'faces': out_triangles.tolist(),
        'watertight': True,
        'source_face_count': faces_total,
        'result_face_count': len(out_triangles),
        'volume': float(tri_union.volume),
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description='Real Manifold3D CPU CSG sculpt-reference worker')
    parser.add_argument('--input',type=Path,required=True,help='Local JSON of 2+ solid triangle meshes')
    parser.add_argument('--output',type=Path,required=True,help='New JSON, never overwrite input')
    args=parser.parse_args(argv)
    src=args.input.expanduser().resolve();out=args.output.expanduser().resolve()
    if src == out or out.exists() or not src.is_file():
        parser.error('Require distinct input file and new output path')
    if src.stat().st_size > 150_000_000:
        parser.error('Input exceeds 150MB safety cap')
    result=process(json.loads(src.read_text(encoding='utf8')))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf8',dir=out.parent,prefix='manifold-',suffix='.json',delete=False) as f:
        temp=Path(f.name)
        json.dump(result,f,separators=(',',':'),allow_nan=False)
    try:
        if out.exists():raise FileExistsError('Output appeared; refusing overwrite')
        os.replace(temp,out)
    finally:
        temp.unlink(missing_ok=True)
    print(f'[Manifold3D CPU] {len(result["source_objects"])} static meshes, {result["result_face_count"]} output triangles, sculpt reference only')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(f'[Manifold3D CPU] {type(e).__name__}: {e}',file=sys.stderr)
        raise SystemExit(2)
