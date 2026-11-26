#!/usr/bin/env python3
"""Safe Blender 4.5+ <-> PyMeshLab CPU static mesh filter.

Before Rigger/skin/morph stages: every mesh is audited; only cleanable static
surfaces are replaced with topologically cleaned copies. Original .blend is
never modified. The optional gate is intentionally no-op on protected meshes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def parse():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--output-json',required=True)
    p.add_argument('--python-bin',required=True,help='External CPU Python with PyMeshLab installed')
    p.add_argument('--clean-static',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    p1,p2=Path(a.blend).resolve(),Path(a.output_blend).resolve()
    if not p1.is_file() or p1.suffix.lower()!='.blend':p.error('Blender input scene missing')
    if p1==p2 or p2.suffix.lower()!='.blend':p.error('Output must be a new .blend')
    if p2.exists():p.error('Refusing overwrite of existing scene')
    report=Path(a.output_json).resolve()
    if report in (p1,p2) or report.exists():p.error('Report must be a new distinct JSON')
    return a,p1,p2,report


def eligible(obj):
    import bpy
    if obj.type!='MESH':return False,'not_mesh'
    mesh=obj.data
    if obj.name.startswith(('SCULPT_','ZA_','MPFB_','TRELLIS_','IM_LOD_','IM_SOURCE_','LOD_SOURCE_')) or obj.get('non_exportable_reference') or obj.get('reference_only'):
        return False,'reference'
    if obj.parent and obj.parent.type=='ARMATURE':return False,'parent_armature'
    if obj.vertex_groups or any(v.groups for v in mesh.vertices):return False,'skinning_weights'
    if any(m.type=='ARMATURE' for m in obj.modifiers):return False,'armature_modifier'
    if obj.modifiers:return False,'other_modifiers'
    if mesh.shape_keys:return False,'shape_keys'
    if len(mesh.uv_layers)>0 or len(mesh.color_attributes)>0:return False,'UV_or_color'
    if mesh.users>1:return False,'shared_mesh'
    if len(mesh.materials)>1 or any(f.material_index!=0 for f in mesh.polygons):
        return False,'mixed_materials'
    if len(mesh.vertices)<3 or len(mesh.polygons)<2:return False,'too_small'
    if any(len(f.vertices)!=3 for f in mesh.polygons):return False,'nontriangular_faces'
    if len({f.use_smooth for f in mesh.polygons})>1:return False,'mixed_shading'
    permitted={'position','material_index','sharp_face','sharp_edge','crease_edge','crease_vert'}
    if any(a.name not in permitted for a in mesh.attributes):return False,'custom_mesh_attributes'
    return True,'static_safe'


def payload(mesh):
    return {'vertices':[list(v.co) for v in mesh.vertices],
            'faces':[list(p.vertices) for p in mesh.polygons]}


def apply_clean(obj,data):
    mesh=obj.data
    mats=list(mesh.materials)
    shade=bool(mesh.polygons[0].use_smooth) if len(mesh.polygons) else False
    name=mesh.name
    mesh.clear_geometry()
    mesh.from_pydata(data['vertices'],[],data['faces'])
    mesh.update()
    for mat in mats:
        if mat and mat.name not in [m.name for m in mesh.materials if m]:mesh.materials.append(mat)
    for f in mesh.polygons:f.use_smooth=shade
    mesh.name=name
    if len(mesh.vertices)!=data['new_vertices'] or len(mesh.polygons)!=data['new_triangles']:
        raise RuntimeError('Blender geometry update failed')


def main():
    import bpy
    a,src,out,report=parse()
    bpy.ops.wm.open_mainfile(filepath=str(src))
    exe=Path(a.python_bin).expanduser().resolve()
    if not exe.is_file():raise FileNotFoundError('CPU Python missing: '+str(exe))
    script=Path(__file__).with_name('pymeshlab_cpu_worker.py')
    items=[];count=0
    with tempfile.TemporaryDirectory(prefix='monster-pymeshlab-cpu-') as td:
        d=Path(td)
        for obj in sorted((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:o.name):
            okay,reason=eligible(obj)
            entry={'name':obj.name,'eligible':okay,'reason':reason,
                   'faces':len(obj.data.polygons),'vertices':len(obj.data.vertices),'changed':False}
            if not okay:
                items.append(entry);continue
            ip=d/'source.json';op=d/'cleaned.json'
            ip.write_text(json.dumps(payload(obj.data),separators=(',',':')),encoding='utf8')
            if op.exists():op.unlink()
            res=subprocess.run([str(exe),str(script),'--input',str(ip),'--output',str(op)],
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=240)
            if res.returncode!=0 or not op.is_file():
                raise RuntimeError('PyMeshLab processing failed for '+obj.name+': '+res.stderr[-900:])
            cleaned=json.loads(op.read_text(encoding='utf8'))
            entry['after_faces']=cleaned['new_triangles'];entry['after_vertices']=cleaned['new_vertices']
            entry['changed']=bool(cleaned['changed'])
            if a.clean_static and entry['changed']:
                apply_clean(obj,cleaned)
                count+=1
            items.append(entry)
    out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'mode':'clean_static' if a.clean_static else 'audit',
                                  'changed_meshes':count,'items':items},ensure_ascii=False,indent=2),encoding='utf8')
    print('Safe PyMeshLab meshes cleaned:',count,'total:',len(items))

if __name__=='__main__':main()
