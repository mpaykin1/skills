#!/usr/bin/env python3
"""Blender CPU bridge: apply Pillow-produced PBR textures after xatlas UVs.

Only a new material copy is edited. Original armature, vertex topology,
mesh UVs, morph coordinates, actions and skins are verified unchanged.
Existing image-based or complex artist materials are never overwritten.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,struct,subprocess,sys,tempfile
from pathlib import Path


def parse():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--source-glb',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--output-glb',required=True)
    p.add_argument('--texture-dir',required=True)
    p.add_argument('--python-bin',default=sys.executable)
    p.add_argument('--size',type=int,default=512)
    p.add_argument('--wetness',type=float,default=0.35)
    p.add_argument('--allow-noop',action='store_true')
    p.add_argument('--uv-name',default='XATLAS_CPU')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    inp=[Path(a.blend).resolve(),Path(a.source_glb).resolve()]
    outputs=[Path(a.output_blend).resolve(),Path(a.output_glb).resolve()]
    if any(not x.is_file() for x in inp):p.error('Source BLEND/GLB missing')
    if len(set(inp+outputs))!=4 or any(x.exists() for x in outputs):p.error('Output must be new and distinct')
    if a.size not in (128,256,512,1024,2048):p.error('Invalid texture resolution')
    if not math.isfinite(a.wetness) or not 0<=a.wetness<=1:p.error('Wetness 0..1 required')
    return a


def fingerprint(ob):
    h=hashlib.sha256();mesh=ob.data
    h.update(struct.pack('<I',len(mesh.vertices)))
    for v in mesh.vertices:
        h.update(struct.pack('<3f',*v.co))
        for grp in v.groups:h.update(struct.pack('<If',grp.group,grp.weight))
    for poly in mesh.polygons:
        h.update(struct.pack('<II',poly.material_index,len(poly.vertices)))
        for idx in poly.vertices:h.update(struct.pack('<I',idx))
    for uv in mesh.uv_layers:
        h.update(uv.name.encode())
        for loop in uv.data:h.update(struct.pack('<2f',*loop.uv))
    if mesh.shape_keys:
        for key in mesh.shape_keys.key_blocks:
            h.update(key.name.encode())
            for v in key.data:h.update(struct.pack('<3f',*v.co))
    for vg in ob.vertex_groups:h.update(vg.name.encode())
    return h.digest()


def material_ok(mat):
    if not mat:return False
    if not mat.use_nodes:return False
    nodes=mat.node_tree.nodes
    # An artist-authored shader stays intact, even if texture-less.
    if any(n.type=='TEX_IMAGE' for n in nodes):return False
    if any(n.type not in ('BSDF_PRINCIPLED','OUTPUT_MATERIAL') for n in nodes):return False
    if any(n.type=='BSDF_PRINCIPLED' for n in nodes) is False:return False
    bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    if bsdf.inputs['Base Color'].is_linked or bsdf.inputs['Roughness'].is_linked:return False
    return True


def triangles_payload(ob,slot,uv_layer,size,wetness):
    mesh=ob.data
    mesh.calc_loop_triangles()
    polys=mesh.polygons
    # Angle deviation in rest-pose surface: deterministic, non-random,
    # anatomically geometry-derived creases (not noise textures).
    from mathutils import Vector
    normal_sum=[Vector((0,0,0)) for _ in mesh.vertices]
    counts=[0]*len(mesh.vertices)
    for face in polys:
        for v in face.vertices:
            normal_sum[v]+=face.normal
            counts[v]+=1
    mean=[normal_sum[i].normalized() if counts[i] else Vector((0,0,1)) for i in range(len(counts))]
    raw=[0.0]*len(mean)
    for face in polys:
        for v in face.vertices:
            raw[v]+=max(0.,1.-max(-1.,min(1.,face.normal.dot(mean[v]))))
    raw=[raw[i]/max(1,counts[i]) for i in range(len(raw))]
    # Preserve subtle shading on smooth muscle surfaces; no invented dirt/noise.
    scale=max(sorted(raw)[int(.95*(len(raw)-1))],0.04) if raw else 0.04
    vals=[max(0.0,min(1.0,x/scale)) for x in raw]
    triangles=[]
    for tri in mesh.loop_triangles:
        if polys[tri.polygon_index].material_index!=slot:continue
        loops=list(tri.loops);vidx=list(tri.vertices)
        triangles.append({'uv':[[float(v) for v in uv_layer.data[li].uv] for li in loops],
                          'curvature':[float(vals[vi]) for vi in vidx]})
    if not triangles:raise ValueError('Material slot has no triangles')
    mat=ob.material_slots[slot].material
    bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    color=bsdf.inputs['Base Color'].default_value
    return {'format':'monster-pillow-pbr-v1','size':size,'wetness':wetness,
            'base_color':list(map(float,color[:3])),
            'roughness':float(bsdf.inputs['Roughness'].default_value),
            'triangles':triangles}


def attach_material(bpy,ob,slot,old_mat,albedo_file,rough_file,uvname):
    mat=old_mat.copy()
    mat.name=f'CPU_PBR_{ob.name[:26]}_{slot}'
    bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    nt=mat.node_tree
    # Explicit UV node ensures source xatlas set is the one exported by glTF.
    uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map=uvname;uv.label='Original CPU xatlas atlas'
    alb=nt.nodes.new('ShaderNodeTexImage');alb.image=bpy.data.images.load(str(albedo_file),check_existing=False)
    alb.image.name='CPU_Albedo_'+str(slot)+'_'+ob.name;alb.image.colorspace_settings.name='sRGB'
    alb.image.pack()
    nt.links.new(uv.outputs['UV'],alb.inputs['Vector'])
    nt.links.new(alb.outputs['Color'],bsdf.inputs['Base Color'])
    rough=nt.nodes.new('ShaderNodeTexImage');rough.image=bpy.data.images.load(str(rough_file),check_existing=False)
    rough.image.name='CPU_Rough_'+str(slot)+'_'+ob.name;rough.image.colorspace_settings.name='Non-Color'
    rough.image.pack()
    separate=nt.nodes.new('ShaderNodeSeparateColor');separate.mode='RGB'
    nt.links.new(uv.outputs['UV'],rough.inputs['Vector'])
    nt.links.new(rough.outputs['Color'],separate.inputs['Color'])
    nt.links.new(separate.outputs['Green'],bsdf.inputs['Roughness'])
    ob.material_slots[slot].material=mat


def main():
    import bpy
    from xatlas_blender_bridge import glb_semantics
    from blender_sculpt_bridge import is_monster_mesh,save_selected_glb
    a=parse();src=Path(a.blend).resolve();baseline=glb_semantics(Path(a.source_glb).resolve())
    check=subprocess.run([a.python_bin,'-c',"from PIL import Image,__version__;assert __version__=='12.3.0'"],
                         capture_output=True,text=True,check=False,timeout=30)
    if check.returncode:raise RuntimeError('Pillow==12.3.0 not found. Run scripts/install_pillow_cpu.py --install. '+check.stderr[-250:])
    bpy.ops.wm.open_mainfile(filepath=str(src))
    rig=bpy.data.objects.get('MONSTER_RIG')
    if not rig or rig.type!='ARMATURE':raise RuntimeError('Source MONSTER_RIG missing')
    targets=[ob for ob in bpy.data.objects if is_monster_mesh(ob,rig)]
    if not targets:raise RuntimeError('No exportable original monster geometry')
    fingerprints={ob.name:fingerprint(ob) for ob in targets}
    actions=set(bpy.data.actions.keys());bones=tuple(b.name for b in rig.data.bones)
    changed=[];skips=[];texdir=Path(a.texture_dir).resolve()
    with tempfile.TemporaryDirectory(prefix='monster-pillow-pbr-') as temp:
        temp=Path(temp)
        for ob in targets:
            if ob.hide_render or ob.get('non_exportable_reference') or ob.data.users!=1:
                skips.append(ob.name+': hidden/reference/shared datablock');continue
            uv=ob.data.uv_layers.get(a.uv_name)
            if not uv:
                skips.append(ob.name+': no xatlas UV layer (existing artist UV untouched)');continue
            for slot in range(len(ob.material_slots)):
                mat=ob.material_slots[slot].material
                if not material_ok(mat):
                    skips.append(ob.name+': original material complex/textured; preserved');continue
                data=triangles_payload(ob,slot,uv,a.size,a.wetness)
                stem=re.sub('[^a-zA-Z0-9_-]','_',ob.name)[:50]+'-'+str(slot)+'-'+hashlib.sha1(ob.name.encode()).hexdigest()[:8]
                albedo=texdir/(stem+'-albedo.png');rough=texdir/(stem+'-roughness.png')
                if albedo.exists() or rough.exists():raise RuntimeError('Refusing to overwrite existing artist texture')
                inp=temp/'input.json';inp.write_text(json.dumps(data,separators=(',',':')),encoding='utf8')
                cmd=[a.python_bin,str(Path(__file__).with_name('pillow_pbr_cpu_worker.py')),
                    '--input',inp,'--albedo',albedo,'--roughness',rough]
                subprocess.run([str(x) for x in cmd],check=True,timeout=1800)
                attach_material(bpy,ob,slot,mat,albedo,rough,uv.name)
                changed.append(stem)
    if not changed and not a.allow_noop:raise RuntimeError('No eligible untextured xatlas muscles. Use --xatlas-uv first; existing image materials were protected. '+str(skips[:4]))
    if set(bpy.data.actions.keys())!=actions or tuple(b.name for b in rig.data.bones)!=bones:
        raise RuntimeError('Rig or animation actions changed')
    for ob in targets:
        if fingerprint(ob)!=fingerprints[ob.name]:raise RuntimeError('Geometry, UV, morph or weights changed: '+ob.name)
    out=Path(a.output_blend).resolve();dst=Path(a.output_glb).resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    dst.parent.mkdir(parents=True,exist_ok=True)
    save_selected_glb(dst,rig,targets)
    final=glb_semantics(dst)
    protected=('animations','skins','morph_primitive_targets','morph_target_names','mesh_count','extensions_required')
    altered=[k for k in protected if baseline[k]!=final[k]]
    if altered:
        out.unlink(missing_ok=True);dst.unlink(missing_ok=True)
        raise RuntimeError('PBR conversion changed protected GLB: '+', '.join(altered))
    if changed and (len(final['doc'].get('images',[]))==0 or len(final['doc'].get('textures',[]))==0):
        out.unlink(missing_ok=True);dst.unlink(missing_ok=True)
        raise RuntimeError('Pillow textures missing from GLB after export')
    print('[Pillow] Preserved rig and motion; CPU texture atlas count:',len(changed),'GLB:',dst)

if __name__=='__main__':main()
