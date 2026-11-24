#!/usr/bin/env python3
"""CPU-only SciPy graph diffusion for newly generated skeletal skin weights.

This worker is deliberately independent of Blender's Python: input/output JSON
is exchanged with cpu_skinning_blender.py.  It never modifies geometry, meshes,
UVs, morph targets, materials, bones, or old approved vertex groups.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path


def smooth_skin_weights(data: dict) -> dict:
    import numpy as np
    from scipy import sparse

    xyz = np.asarray(data['vertices'], dtype=np.float64)
    raw = np.asarray(data['weights'], dtype=np.float64)
    faces = data['faces']
    bones = data['bones']
    iterations = int(data.get('iterations', 3))
    strength = float(data.get('strength', 0.35))
    cap = int(data.get('max_influences', 4))
    if xyz.ndim != 2 or xyz.shape[1] != 3 or raw.ndim != 2:
        raise ValueError('Expected Nx3 vertices and NxB weights')
    n = len(xyz)
    if not 3 <= n <= 150000 or not 1 <= len(bones) <= 128 or n * len(bones) > 8_000_000:
        raise ValueError('Mesh size or bone count exceeds conservative CPU budget')
    if raw.shape != (n, len(bones)) or len(set(bones)) != len(bones) or not all(isinstance(x,str) and x for x in bones):
        raise ValueError('Weight columns must match unique bone names')
    if not 1 <= cap <= 4 or not 1 <= iterations <= 8 or not 0 <= strength <= 0.65:
        raise ValueError('Allowed: 1..4 influences, 1..8 iterations, 0..0.65 strength')
    if not np.isfinite(xyz).all() or not np.isfinite(raw).all() or (raw < 0).any():
        raise ValueError('Nonfinite vertices or invalid weights')
    base_sum = raw.sum(axis=1)
    if np.any(base_sum <= 1e-8):
        raise ValueError('Unweighted vertices: repair initial Blender skin before smoothing')
    base = raw / base_sum[:,None]
    if not faces or len(faces) > 300000:
        raise ValueError('No polygon topology or geometry exceeds CPU budget')

    # Build connected surface graph only from polygon edges, never Euclidean
    # nearest neighbors: nearby but disconnected muscle surfaces must not bleed.
    sources, destinations, edge_values = [], [], []
    for poly in faces:
        if not isinstance(poly,list) or not 3 <= len(poly) <= 256:
            raise ValueError('Invalid polygon vertex count')
        if len(set(poly)) != len(poly):
            raise ValueError('Repeated vertex in polygon')
        if any(type(v) is not int or v < 0 or v >= n for v in poly):
            raise ValueError('Polygon references missing vertex')
        for a,b in zip(poly, poly[1:]+poly[:1]):
            dist = float(np.linalg.norm(xyz[a] - xyz[b]))
            if not math.isfinite(dist) or dist < 1e-10:
                raise ValueError('Degenerate edge: repair geometry with Trimesh/PyMeshLab first')
            # Edge length-aware; very short edges cannot dominate arbitrarily.
            val = 1.0 / dist
            sources.extend((a,b));destinations.extend((b,a));edge_values.extend((val,val))
    graph = sparse.coo_matrix((edge_values,(sources,destinations)),shape=(n,n),dtype=np.float64).tocsr()
    # Two faces sharing a border generate duplicate edges: graph sums weights,
    # which is desirable for adjacent vertices with stronger connectivity.
    degrees = np.asarray(graph.sum(axis=1)).reshape(-1)
    nonisolated = degrees > 0
    normalized = sparse.diags(1.0 / np.maximum(degrees,1e-12),format='csr') @ graph
    out = base.copy()
    # Lock strongly bound vertices, retaining the muscle attachment near bones.
    anchors = base.max(axis=1) >= 0.995
    for _ in range(iterations):
        diffused = normalized @ out
        proposed = (1.0 - strength) * out + strength * diffused
        proposed[anchors | ~nonisolated] = base[anchors | ~nonisolated]
        if not np.isfinite(proposed).all():
            raise RuntimeError('Nonfinite weights during SciPy sparse diffusion')
        out = proposed
    if cap < out.shape[1]:
        keep = np.argpartition(out,-cap,axis=1)[:,-cap:]
        selected = np.zeros_like(out)
        np.put_along_axis(selected,keep,np.take_along_axis(out,keep,axis=1),axis=1)
        out = selected
    norm = out.sum(axis=1)
    if np.any(norm <= 1e-9):
        raise RuntimeError('Weight normalization failed; refusing export')
    out /= norm[:,None]
    if (out < -1e-10).any() or np.max(np.abs(out.sum(axis=1)-1)) > 1e-6:
        raise RuntimeError('Invalid normalized skinning after optimization')
    # A bounded local filter, not full re-rigging of an approved creature.
    if np.max(np.abs(out-base)) > 0.76:
        raise RuntimeError('Skin smoothing unexpectedly changed an attachment too strongly')
    return {
        'format':'monster-anatomy-scipy-skin-v1',
        'bones':bones,
        'weights':out.tolist(),
        'vertices':n,
        'boundary_anchor_count':int(anchors.sum()),
        'edges':int(graph.nnz // 2),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description='SciPy CPU sparse-mesh skin-weight smoother')
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    if args.input.expanduser().resolve()==args.output.expanduser().resolve():p.error('Input and output must be different')
    payload=json.loads(args.input.read_text(encoding='utf8'))
    output=smooth_skin_weights(payload)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,separators=(',',':'),allow_nan=False),encoding='utf8')
    print(f"[scipy] CPU weight diffusion: {output['vertices']} vertices, {output['edges']} connected edges")

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,RuntimeError,ImportError) as e:
        print(f'[scipy] failed: {e}',file=sys.stderr)
        raise SystemExit(2)
