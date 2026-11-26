#!/usr/bin/env python3
"""Non-destructive Blender <-> official Manifold3D CPU Boolean sculpt guide.

Read source mesh REST GEOMETRY ONLY (including existing rigged/UV textured sources),
run Manifold3D in separate Python, and add a NON-EXPORTABLE reference to a new
scene. NEVER alters a source mesh, vertex group, material, UV, morph or clip.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def args():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--python-bin',default=sys.executable)
    p.add_argument('--objects',default='',help='Comma-separated exact mesh names; otherwise select muscle/body patterns')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    source=Path(a.blend).resolve();target=Path(a.output_blend).resolve()
    if not source.is_file() or source.suffix.lower()!='.blend' or target.suffix.lower()!='.blend' or source==target or target.exists():
        p.error('Read an existing .blend and write a DISTINCT new .blend')
    return a,source,target


def is_eligible(ob):
    if ob.type!='MESH':return False,'not_mesh'
    if ob.name.startswith(('ZA_','MPFB_','SCULPT_','TRELLIS_','LOD_SOURCE_','MANIFOLD_')):
        return False,'reference'
    if ob.get('non_exportable_reference') or ob.get('reference_only') or ob.hide_render:
        return False,'reference'
    data=ob.data
    # Mesh source is strictly read-only. Rigging/UV/materials are *ignored* in
    # the guide snapshot, never transferred or replaced on the original.
    if any(m.type!='ARMATURE' for m in ob.modifiers):return False,'non_armature_modifier'
    if len(data.vertices)<4 or len(data.polygons)<4:return False,'too_small'
    return True,'read_only_rest_geometry'


def main():
    import bpy
    a,src,dst=args()
    bpy.ops.wm.open_mainfile(filepath=str(src))
    selected={x.strip() for x in a.objects.split(',') if x.strip()}
    if a.objects and len(selected)<2:raise ValueError('Specify at least 2 objects for a Boolean union')
    if selected:
        unknown=selected-set(bpy.data.objects.keys())
        if unknown:raise ValueError('Unknown selected Blender objects: '+str(sorted(unknown)))
        objects=[bpy.data.objects[name] for name in sorted(selected)]
    else:
        def chosen(ob):
            n=ob.name.lower()
            return bool(ob.get('manifold_fuse')) or n.startswith(('muscle_','body_','shell_',
              'pectoral','deltoid_','quadriceps_','forearm flexors_', 'bent thoracic erectors'))
        objects=[ob for ob in bpy.data.objects if ob.type=='MESH' and chosen(ob)]
        objects.sort(key=lambda ob:ob.name)
    if len(objects)<2:raise ValueError('No 2+ selected static muscle/body meshes; tag manifold_fuse or pass --objects')
    data=[]
    for ob in objects:
        yes,why=is_eligible(ob)
        if not yes:raise ValueError(f'{ob.name}: not safe for topology-changing CPU Boolean ({why}); original remains untouched')
        if ob.matrix_world.determinant()<0:
            raise ValueError(f'{ob.name}: negative-scale mirrored geometry; apply scale before Manifold')
        vertices=[list(ob.matrix_world@v.co) for v in ob.data.vertices]
        # Triangulation is virtual and does not rewrite original quads/ngons.
        ob.data.calc_loop_triangles()
        faces=[list(t.vertices) for t in ob.data.loop_triangles]
        data.append({'name':ob.name,'vertices':vertices,'faces':faces})
    with tempfile.TemporaryDirectory(prefix='monster-manifold-') as tmp:
        tmp=Path(tmp)
        feed=tmp/'input.json';result=tmp/'result.json'
        feed.write_text(json.dumps({'meshes':data},separators=(',',':')),encoding='utf8')
        worker=Path(__file__).with_name('manifold3d_cpu_worker.py')
        cmd=[a.python_bin,str(worker),'--input',str(feed),'--output',str(result)]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=900,check=False)
        if proc.returncode or not result.is_file():
            raise RuntimeError('Manifold3D CPU worker failed: '+proc.stderr[-1200:])
        fused=json.loads(result.read_text(encoding='utf8'))
    if fused.get('format')!='manifold-sculpt-guide-v1' or not fused.get('watertight'):
        raise RuntimeError('Invalid real Manifold CPU output')
    collection=bpy.data.collections.get('MANIFOLD_SCULPT_REFERENCES')
    if not collection:
        collection=bpy.data.collections.new('MANIFOLD_SCULPT_REFERENCES')
        bpy.context.scene.collection.children.link(collection)
    if 'MANIFOLD_SCULPT_REFERENCE' in bpy.data.objects:
        raise RuntimeError('Sculpt guide already exists; refusing overwrite')
    mesh=bpy.data.meshes.new('MANIFOLD_SCULPT_REFERENCE_MESH')
    mesh.from_pydata(fused['vertices'],[],fused['faces']);mesh.update()
    ob=bpy.data.objects.new('MANIFOLD_SCULPT_REFERENCE',mesh)
    collection.objects.link(ob)
    ob['non_exportable_reference']=True
    ob['reference_only']=True
    ob['manifold_cpu_union']=True
    ob['manifold_source_names']=';'.join(fused['source_objects'])
    ob.hide_render=True
    ob.display_type='WIRE'
    ob.show_in_front=True
    dst.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(dst))
    if not dst.is_file():raise RuntimeError('Sculpt guide blend was not created')
    print('[Manifold3D CPU] Added editable, visible wire sculpt-guide to new BLEND:',dst)

if __name__=='__main__':main()
