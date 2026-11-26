#!/usr/bin/env python3
"""Bring original TRELLIS.2 PBR draft GLB into the ANATOMIC monster .blend.

Preserves original 3D detail/materials; imported mesh stays a non-exported
sculptural reference, never silently overrides rigged muscle assets.
Computes real spatial distances from the draft mesh to Z-Anatomy guide points.
All positions are approximate: a single image cannot recover hidden anatomy.

blender --background --python scripts/trellis_surface_bridge.py -- \\
 --blend scene.blend --trellis-glb generated.glb --output-blend guided.blend \\
 --output-json draft_landmarks.json
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree


def bounds(meshes):
    pts=[obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not pts:raise RuntimeError('No source mesh bounding boxes')
    lo=Vector(tuple(min(p[k] for p in pts) for k in range(3)))
    hi=Vector(tuple(max(p[k] for p in pts) for k in range(3)))
    return lo,hi


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--blend',required=True)
    ap.add_argument('--trellis-glb',required=True)
    ap.add_argument('--output-blend',required=True)
    ap.add_argument('--output-json',required=True)
    ap.add_argument('--rotate-z',type=float,default=0.0,help='manual Z rotation degrees; default 0')
    ap.add_argument('--fit-multiplier',type=float,default=1.0,help='artistic uniform fit to rig height')
    opts=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not .1<=opts.fit_multiplier<=10:ap.error('--fit-multiplier must be 0.1..10')
    for arg in (opts.blend,opts.trellis_glb):
        if not Path(arg).is_file():ap.error('missing input '+arg)
    bpy.ops.wm.open_mainfile(filepath=str(Path(opts.blend).resolve()))
    rig=bpy.data.objects.get('MONSTER_RIG')
    if rig is None or rig.type!='ARMATURE':raise RuntimeError('Original MONSTER_RIG missing; cannot preserve creature identity')
    body=[o for o in bpy.data.objects if o.type=='MESH' and o.parent==rig
          and not o.get('reference_only') and not o.get('non_exportable_reference')
          and not o.name.startswith(('ZA_', 'MPFB_', 'SCULPT_', 'TRELLIS_'))]
    if not body:raise RuntimeError('No existing rigged monster meshes: refusing to replace character')
    target_lo,target_hi=bounds(body)
    target_center=(target_lo+target_hi)*.5
    target_height=max(1e-6,target_hi.z-target_lo.z)
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(Path(opts.trellis_glb).resolve()))
    imported=set(bpy.data.objects)-before
    source_mesh=[obj for obj in imported if obj.type=='MESH']
    if not source_mesh:raise RuntimeError('TRELLIS.2 GLB had no polygon meshes')
    source_lo,source_hi=bounds(source_mesh)
    source_height=source_hi.z-source_lo.z
    if source_height<1e-5:raise RuntimeError('TRELLIS.2 GLB height is zero')
    source_center=(source_hi+source_lo)*.5
    scale=target_height/source_height*opts.fit_multiplier
    transform=(Matrix.Translation(target_center)
               @ Matrix.Rotation(math.radians(opts.rotate_z),4,'Z')
               @ Matrix.Scale(scale,4)
               @ Matrix.Translation(-source_center))
    # Multiplying only parentless roots avoids double transforming child meshes.
    roots=[o for o in imported if o.parent not in imported]
    for root in roots:root.matrix_world=transform @ root.matrix_world
    bpy.context.view_layer.update()
    col=bpy.data.collections.get('TRELLIS_REFERENCE_NON_EXPORT')
    if col is None:
        col=bpy.data.collections.new('TRELLIS_REFERENCE_NON_EXPORT')
        bpy.context.scene.collection.children.link(col)
    for obj in imported:
        for c in list(obj.users_collection):c.objects.unlink(obj)
        col.objects.link(obj)
        obj['reference_only']=True
        obj['non_exportable_reference']=True
        obj['trellis_static_unrigged']=True
        obj['trellis_source_glb']=str(Path(opts.trellis_glb).resolve())
        obj.hide_render=True
        obj.hide_set(False)
        obj.name='TRELLIS_REF_'+obj.name
    # Sample vertex positions, limiting memory but preserving original meshes in scene.
    total_verts=sum(len(o.data.vertices) for o in source_mesh)
    cap=200000
    step=max(1,math.ceil(total_verts/cap))
    samples=[o.matrix_world @ vert.co for o in source_mesh for j,vert in enumerate(o.data.vertices) if j%step==0]
    index=KDTree(len(samples))
    for i,p in enumerate(samples):index.insert(p,i)
    index.balance()
    rows=[]
    for marker in bpy.data.objects:
        if marker.name.startswith(('ZA_ORIGIN_','ZA_INSERTION_')):
            p=marker.matrix_world.translation
            nearest,vid,distance=index.find(p)
            rows.append({'name':marker.name,'distance_m':round(float(distance),5),
                         'relative_to_height':round(float(distance/target_height),5),
                         'candidate_xyz':[round(float(v),5) for v in nearest]})
    row={'source':'Microsoft TRELLIS.2','draft_glb':str(Path(opts.trellis_glb).resolve()),
         'mode':'sculptural reference; unrigged; not exported to gameplay GLB',
         'rig':'MONSTER_RIG','source_mesh_count':len(source_mesh),
         'source_vertices':total_verts,'landmarks':rows,
         'scale_factor':scale,'rotate_z_degrees':opts.rotate_z,
         'warning':'Distances are geometric approximations, not recovered anatomy or measured muscle insertions.'}
    scene=Path(opts.output_blend).resolve();scene.parent.mkdir(parents=True,exist_ok=True)
    result=Path(opts.output_json).resolve();result.parent.mkdir(parents=True,exist_ok=True)
    result.write_text(json.dumps(row,indent=2,ensure_ascii=False),encoding='utf8')
    bpy.ops.wm.save_as_mainfile(filepath=str(scene))
    print('TRELLIS.2 aligned draft reference:',scene,'markers:',len(rows))

if __name__=='__main__':main()
