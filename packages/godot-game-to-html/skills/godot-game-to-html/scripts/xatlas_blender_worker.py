"""Blender background worker. Uses installed xatlas Python bindings, not a fake unwrap.

Only static triangle meshes. Keeps original UV0, geometry, materials and
animation data in the .blend derivative. Never modifies the input file.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re
import sys


def args_after_dash():
    if '--' not in sys.argv:raise RuntimeError('Call through xatlas_lightmaps.py')
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--bake-ao',action='store_true')
    p.add_argument('--export-glb',action='store_true')
    p.add_argument('--size',type=int,default=512)
    p.add_argument('--samples',type=int,default=24)
    p.add_argument('--max-faces',type=int,default=100000)
    return p.parse_args(sys.argv[sys.argv.index('--')+1:])


def is_static_mesh(o):
    if o.type!='MESH':return False,'not a mesh'
    if o.data.shape_keys or o.vertex_groups or o.find_armature():return False,'deform/skin'
    if o.animation_data or any(p.animation_data for p in o.parent_recursive):return False,'animated'
    if o.modifiers:return False,'modifiers present'
    if not o.data.uv_layers:return False,'original UV0 missing (skip to preserve materials)'
    if len(o.data.uv_layers)>1:return False,'existing UV2 preserved'
    if len(o.data.polygons)==0:return False,'empty'
    if any(len(poly.vertices)!=3 for poly in o.data.polygons):return False,'requires triangles'
    return True,''


def atlas_obj(o,xatlas,np):
    mesh=o.data
    mesh.calc_loop_triangles()
    triangles=list(mesh.loop_triangles)
    if not triangles:return None
    verts=np.asarray([tuple(v.co) for v in mesh.vertices],dtype=np.float32)
    faces=np.asarray([tuple(t.vertices) for t in triangles],dtype=np.uint32)
    # Actual xatlas; returns new-vertex-to-old mapping, triangle indices, UVs.
    vmapping,atlas_faces,uvcoords=xatlas.parametrize(verts,faces)
    if len(atlas_faces)!=len(triangles):raise RuntimeError('xatlas changed triangle count')
    if not np.isfinite(uvcoords).all():raise RuntimeError('xatlas produced NaN/inf UV')
    if (uvcoords<-0.001).any() or (uvcoords>1.001).any():
        raise RuntimeError('xatlas UVs are outside 0..1')
    uv2=mesh.uv_layers.new(name='UV2_xatlas')
    # Blender stores UV values *per face corner*, so chart seams need no
    # destructive splitting of source mesh vertices or its original UV0.
    assigned={}
    for t,faces_uv in zip(triangles,atlas_faces):
        original_loops=list(t.loops)
        for a in faces_uv:
            original_vid=int(vmapping[int(a)])
            matches=[li for li in original_loops if mesh.loops[li].vertex_index==original_vid]
            if len(matches)!=1:raise RuntimeError('xatlas corner-to-vertex mapping mismatch')
            li=matches[0]
            uv=(float(uvcoords[int(a)][0]),float(uvcoords[int(a)][1]))
            if li in assigned and (abs(assigned[li][0]-uv[0])+abs(assigned[li][1]-uv[1])>1e-4):
                raise RuntimeError('UV seam within original polygon; triangulate source first')
            assigned[li]=uv
    if len(assigned)!=len(mesh.loops):raise RuntimeError('Not all UV corners assigned')
    for idx,uv in assigned.items():uv2.data[idx].uv=uv
    mesh.update()
    return {'object':o.name,'triangles':len(triangles),'uv0_preserved':True,
            'uv2':'UV2_xatlas','uv2_corners':len(assigned),'material_names':[m.name if m else None for m in mesh.materials]}


def bake_ao(bpy,o,out,size,samples):
    # Bake to independent sidecar PNG, NOT to baseColor/roughness or game scene.
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=samples
    scene.render.bake.use_clear=True
    scene.render.bake.margin=8
    scene.render.bake.use_selected_to_active=False
    img=bpy.data.images.new('xatlasAO_'+o.name,width=size,height=size,alpha=False)
    img.generated_color=(1.0,1.0,1.0,1.0)
    created=[]
    uv_original=o.data.uv_layers.active
    ao_uv=o.data.uv_layers.get('UV2_xatlas')
    o.data.uv_layers.active=ao_uv
    try:
        if not o.material_slots:
            mat=bpy.data.materials.new('xatlasAO_temp')
            o.data.materials.append(mat)
            created.append(('extra_material',mat,None))
        # Each material slot must have its own active image texture node.
        for slot in o.material_slots:
            if not slot.material:continue
            mat=slot.material
            if not mat.use_nodes:mat.use_nodes=True
            node=mat.node_tree.nodes.new('ShaderNodeTexImage')
            node.name='XATLAS_TEMP_AO_TARGET'
            node.image=img
            mat.node_tree.nodes.active=node
            created.append(('node',mat,node))
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.bake(type='AO',uv_layer='UV2_xatlas')
        safe=re.sub(r'[^A-Za-z0-9_-]+','_',o.name)[:55]
        png=out/(safe+'_AO.png')
        img.filepath_raw=str(png)
        img.file_format='PNG'
        img.save()
        return png.name
    finally:
        o.data.uv_layers.active=uv_original
        for typ,mat,node in reversed(created):
            if typ=='node' and mat and mat.node_tree:
                mat.node_tree.nodes.remove(node)
            elif typ=='extra_material':
                o.data.materials.pop(index=len(o.data.materials)-1)
        bpy.data.images.remove(img)


def run():
    args=args_after_dash()
    try:
        import bpy
        import numpy as np
        import xatlas
    except ImportError as e:
        raise RuntimeError('Blender Python requires xatlas==0.0.11 and numpy; install xatlas in Blender Python first') from e
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()))
    info={'input_name':args.source.name,'uv2_engine':'xatlas','version':'0.0.11',
          'original_source_unchanged':True,'baked_ao':args.bake_ao,'objects':[],'skipped':[]}
    seen=set()
    ao_dir=out/'ao'
    if args.bake_ao:ao_dir.mkdir(exist_ok=True)
    for o in sorted(bpy.context.scene.objects,key=lambda x:x.name):
        ok,why=is_static_mesh(o)
        if not ok:
            if o.type=='MESH':info['skipped'].append({'object':o.name,'reason':why})
            continue
        # Shared datablocks are intentionally handled once. UVs apply to every instance.
        if o.data.as_pointer() in seen:continue
        seen.add(o.data.as_pointer())
        if len(o.data.polygons)>args.max_faces:
            info['skipped'].append({'object':o.name,'reason':'max-faces threshold'})
            continue
        data=atlas_obj(o,xatlas,np)
        if data:
            if args.bake_ao:
                try:data['ao_png']=bake_ao(bpy,o,ao_dir,args.size,args.samples)
                except Exception as err:
                    data['ao_error']=str(err)
                    print('AO bake skipped for',o.name,err,file=sys.stderr)
            info['objects'].append(data)
    if not info['objects']:
        raise RuntimeError('No eligible static triangle meshes; source untouched')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'uv2-source.blend'))
    if args.export_glb:
        bpy.ops.export_scene.gltf(filepath=str(out/'uv2-derivative.glb'),export_format='GLB',export_texcoords=True)
        info['derivative_glb']='uv2-derivative.glb'
        info['warning']='GLB export is not a byte-identical version of input; inspect UV2/materials in renderer before applying.'
    (out/'atlas-manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print('xatlas UV2 generated for',len(info['objects']),'mesh datablocks; original unchanged')


if __name__=='__main__':
    try:run()
    except Exception as e:
        print('ERROR:',e,file=sys.stderr)
        sys.exit(1)
