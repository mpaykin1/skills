#!/usr/bin/env python3
"""External CPU xatlas parametrization -> Blender per-polygon-loop UV data.

No bpy import, no mesh edits, no vertex/face count changes. xatlas may split
vertices internally at chart seams; reverse-map the resulting UVs to Blender
loops (per-face corners) so ORIGINAL skin weights and shape keys remain intact.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys


def remap_uv(triangles, vmapping, atlas_indices, atlas_uv, loop_count):
    """Return a Blender loop-index -> (u,v) map or fail on ambiguous seam splits."""
    if not isinstance(loop_count,int) or not 3 <= loop_count <= 3_000_000:
        raise ValueError('Unreasonable Blender loop count')
    original={}
    for triangle in triangles:
        verts=tuple(int(x) for x in triangle['v'])
        loops=tuple(int(x) for x in triangle['l'])
        if len(verts)!=3 or len(set(verts))!=3 or len(loops)!=3:
            raise ValueError('Triangle must have three different vertex and loop indices')
        if any(n<0 or n>=loop_count for n in loops):
            raise ValueError('Blender loop index out of range')
        key=tuple(sorted(verts))
        if key in original:
            raise ValueError('Duplicate geometric triangles make UV seam transfer ambiguous')
        original[key]=dict(zip(verts,loops))
    if len(atlas_indices)!=len(original):
        raise ValueError('xatlas modified the number of triangles')
    uv_by_loop={}
    matched=set()
    for tri in atlas_indices:
        atlas_vertices=[int(n) for n in tri]
        if len(atlas_vertices)!=3 or any(n<0 or n>=len(vmapping) for n in atlas_vertices):
            raise ValueError('Invalid xatlas output triangle')
        verts=[int(vmapping[n]) for n in atlas_vertices]
        key=tuple(sorted(verts))
        if key not in original or key in matched:
            raise ValueError('Unexpected, missing or duplicated triangle after xatlas')
        matched.add(key)
        src_loops=original[key]
        for out_idx,src_vertex in zip(atlas_vertices,verts):
            loop=src_loops[src_vertex]
            uv=tuple(float(v) for v in atlas_uv[out_idx])
            if len(uv)!=2 or not all(math.isfinite(v) and -0.001<=v<=1.001 for v in uv):
                raise ValueError('Nonfinite/out-of-atlas UVs')
            earlier=uv_by_loop.get(loop)
            # A polygon corner has ONE UV. xatlas may split an n-gon across an
            # internal triangulation diagonal; refuse impossible assignments.
            if earlier is not None and max(abs(a-b) for a,b in zip(earlier,uv))>1e-5:
                raise ValueError('UV seam crosses a non-triangular polygon interior; manual triangulation required')
            uv_by_loop[loop]=uv
    if len(matched)!=len(original) or len(uv_by_loop)!=loop_count:
        raise ValueError('Missing faces/loops in xatlas result')
    return [list(uv_by_loop[n]) for n in range(loop_count)]


def process(data):
    import numpy as np
    import xatlas
    vertices=np.asarray(data['vertices'],dtype=np.float64)
    triangles=data['triangles']
    faces=np.asarray([t['v'] for t in triangles],dtype=np.int32)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or not 3<=len(vertices)<=1_000_000:
        raise ValueError('Invalid vertex matrix')
    if faces.ndim!=2 or faces.shape[1]!=3 or not 1<=len(faces)<=1_000_000:
        raise ValueError('Invalid triangle matrix')
    if not np.all(np.isfinite(vertices)) or np.any(faces<0) or np.any(faces>=len(vertices)):
        raise ValueError('Invalid coordinates or triangle indices')
    if len(set(tuple(sorted(map(int,t))) for t in faces))!=len(faces):
        raise ValueError('Duplicate source triangles')
    vmapping,indices,uvs=xatlas.parametrize(vertices,faces)
    uv=remap_uv(triangles,vmapping,indices,uvs,int(data['loop_count']))
    return {'format':'monster-xatlas-loop-uv-v1','name':data['name'],
            'vertex_count':int(len(vertices)),'triangle_count':int(len(faces)),
            'loop_count':len(uv),'loop_uv':uv,
            'seam_vertex_copies':int(len(vmapping)-len(vertices))}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    inp=Path(a.input).resolve();out=Path(a.output).resolve()
    if inp==out or not inp.is_file():p.error('Existing input and distinct output required')
    data=json.loads(inp.read_text(encoding='utf-8'))
    if data.get('format')!='monster-xatlas-triangles-v1':p.error('Wrong input schema')
    result=process(data)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    print(f"[xatlas] {data['name']} UV created for {result['triangle_count']} triangles; {result['seam_vertex_copies']} internal seam copies, original vertices unchanged")

if __name__=='__main__':
    try: main()
    except (ImportError,ValueError,KeyError,IndexError,TypeError) as exc:
        print('xatlas CPU error:',exc,file=sys.stderr)
        raise SystemExit(2)
