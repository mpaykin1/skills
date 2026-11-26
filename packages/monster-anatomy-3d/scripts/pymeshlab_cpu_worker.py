#!/usr/bin/env python3
"""Isolated, real PyMeshLab CPU cleanup. No Blender Python, no CUDA.

Read/write JSON triangle geometry only. Never accepts materials, morphs or skin.
Upstream implementation: cnr-isti-vclab/PyMeshLab GPL-3.0; external dependency.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def process(payload):
    import numpy as np
    import pymeshlab
    verts=np.asarray(payload['vertices'],dtype=np.float64)
    faces=np.asarray(payload['faces'],dtype=np.int32)
    if verts.ndim!=2 or verts.shape[1]!=3 or faces.ndim!=2 or faces.shape[1]!=3:
        raise ValueError('Expected N x 3 vertices and M x 3 triangles')
    if len(verts)<3 or len(faces)<1 or not np.isfinite(verts).all():
        raise ValueError('Empty or non-finite mesh')
    if faces.min()<0 or faces.max()>=len(verts):
        raise ValueError('Triangle index out of bounds')
    mesh_set=pymeshlab.MeshSet()
    mesh_set.add_mesh(pymeshlab.Mesh(vertex_matrix=verts, face_matrix=faces), 'monster_cpu_static')
    # Real upstream filters: remove exact defects, no smoothing or remeshing.
    mesh_set.meshing_remove_duplicate_vertices()
    mesh_set.meshing_remove_duplicate_faces()
    mesh_set.meshing_remove_null_faces()
    mesh_set.meshing_remove_unreferenced_vertices()
    new=mesh_set.current_mesh()
    v2=new.vertex_matrix()
    f2=new.face_matrix()
    if len(v2)<3 or len(f2)<1 or not np.isfinite(v2).all():
        raise ValueError('Cleanup removed valid geometry')
    if f2.min()<0 or f2.max()>=len(v2) or len(v2)>len(verts) or len(f2)>len(faces):
        raise ValueError('PyMeshLab returned invalid or unexpectedly larger geometry')
    scale=max(float(np.ptp(verts,axis=0).max()),1e-8)
    delta=float(np.max(np.abs(np.stack((verts.min(axis=0),verts.max(axis=0)))-
                              np.stack((v2.min(axis=0),v2.max(axis=0))))))
    if delta>scale*1e-5:
        raise ValueError('Cleanup changed silhouette bounds')
    if len(f2)<len(faces)*.70:
        raise ValueError('Too many faces removed; refuse potential silhouette loss')
    return {'original_vertices':int(len(verts)),'original_triangles':int(len(faces)),
            'vertices':v2.tolist(),'faces':f2.tolist(),
            'new_vertices':int(len(v2)),'new_triangles':int(len(f2)),
            'changed':bool(len(v2)!=len(verts) or len(f2)!=len(faces)),
            'bounds_delta':delta}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    if a.input.resolve()==a.output.resolve():p.error('Input and output must differ')
    if not a.input.is_file():p.error('Input JSON missing')
    payload=json.loads(a.input.read_text(encoding='utf-8'))
    result=process(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    print('PyMeshLab CPU:',result['original_triangles'],'->',result['new_triangles'],'triangles')

if __name__=='__main__':main()
