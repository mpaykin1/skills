#!/usr/bin/env python3
"""CPU-only Blender skinning: preserve original mesh, rig, materials, morphs, clips.

Works on existing .blend with MONSTER_RIG. Never calls CUDA, ML inference,
or any network service. Existing weighted meshes are NOT modified. New meshes
use Blender's built-in heat weights (with deterministic CPU proximity fallback).
"""
from __future__ import annotations
import argparse
import json
import math
import os
import subprocess
import tempfile
import sys
from pathlib import Path


def parse():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--output-glb',default='')
    p.add_argument('--rig',default='MONSTER_RIG')
    p.add_argument('--method',choices=('auto','proximity'),default='auto')
    p.add_argument('--max-influences',type=int,default=4)
    p.add_argument('--scipy-skin-smooth',action='store_true',help='CPU SciPy surface-weight diffusion on newly skinned meshes ONLY')
    p.add_argument('--scipy-python',default=sys.executable,help='External Python with numpy and scipy==1.17.0')
    p.add_argument('--scipy-iterations',type=int,default=3)
    p.add_argument('--scipy-strength',type=float,default=0.35)
    p.add_argument('--overwrite',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not 1<=a.max_influences<=4:p.error('max influences must be 1..4 for glTF skinning')
    if not 1<=a.scipy_iterations<=8 or not 0<=a.scipy_strength<=0.65:
        p.error('SciPy iterations 1..8, strength 0..0.65')
    inp=Path(a.blend).expanduser().resolve();out=Path(a.output_blend).expanduser().resolve()
    if not inp.is_file() or inp.suffix.lower()!='.blend':p.error('Existing Blender .blend file required')
    if out==inp or out.suffix.lower()!='.blend':p.error('Output .blend must differ from input')
    if out.exists() and not a.overwrite:p.error('Output exists; use --overwrite to allow replacement')
    if a.output_glb:
        glb=Path(a.output_glb).expanduser().resolve()
        if glb.suffix.lower()!='.glb' or glb in (inp,out):p.error('GLB output must be a separate .glb')
        if glb.exists() and not a.overwrite:p.error('GLB exists; use --overwrite')
    return a


def skin_eligible(ob,rig):
    if ob.type!='MESH' or len(ob.data.vertices)<10:return False
    if ob.name.startswith(('ZA_','MPFB_','SCULPT_','Z-ANATOMY_','TRELLIS_','LOD_SOURCE_')):return False
    if ob.get('reference_only') or ob.get('non_exportable_reference'):return False
    if ob.hide_render:return False
    if any(m.type=='ARMATURE' and m.object!=rig for m in ob.modifiers):return False
    # Protect any artist-painted weights, even partial or custom-named ones.
    if any(v.groups for v in ob.data.vertices) or len(ob.vertex_groups)>0:return False
    return True


def weighted(ob):
    return any(v.groups for v in ob.data.vertices)


def attach_armature(ob,rig):
    m=next((m for m in ob.modifiers if m.type=='ARMATURE' and m.object==rig),None)
    if m is None:
        m=ob.modifiers.new('CPU Muscle Skinning','ARMATURE');m.object=rig
    old_matrix=ob.matrix_world.copy()
    if ob.parent is None:
        ob.parent=rig
        ob.matrix_world=old_matrix
    elif ob.parent!=rig:
        # Do not change a non-rig parent hierarchy; armature modifier is enough.
        pass


def heat_skin(bpy,ob,rig):
    """Blender bone heat is CPU-side. Failure means fallback, never partial output."""
    prev=bpy.context.view_layer.objects.active
    old_matrix=ob.matrix_world.copy()
    old_parent=ob.parent
    old_parent_inverse=ob.matrix_parent_inverse.copy()
    try:
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        for x in bpy.context.selected_objects:x.select_set(False)
        ob.select_set(True);rig.select_set(True)
        bpy.context.view_layer.objects.active=rig
        bpy.ops.object.parent_set(type='ARMATURE_AUTO',keep_transform=True)
        if not weighted(ob):raise RuntimeError('Bone heat produced no vertex groups')
        ob.matrix_world=old_matrix
        return True
    except Exception:
        # This stage is only called for initially unweighted meshes.
        for vg in list(ob.vertex_groups):ob.vertex_groups.remove(vg)
        for mod in list(ob.modifiers):
            if mod.type=='ARMATURE' and mod.object==rig:ob.modifiers.remove(mod)
        ob.parent=old_parent
        ob.matrix_parent_inverse=old_parent_inverse
        ob.matrix_world=old_matrix
        return False
    finally:
        for x in bpy.context.selected_objects:x.select_set(False)
        if prev and prev.name in bpy.data.objects:bpy.context.view_layer.objects.active=prev


def nearest_bone_weights(point,segments,k):
    ranked=[]
    for name,a,b,length in segments:
        seg=b-a
        t=max(0.,min(1.,float((point-a).dot(seg))/max(1e-12,float(seg.length_squared))))
        distance=float((point-(a+seg*t)).length)
        # Scale-aware falloff, no neural inference. Avoid 0/0 at bone centers.
        score=1.0/(distance+max(0.01,length*0.08))**3
        ranked.append((score,name))
    ranked.sort(key=lambda z:z[0],reverse=True)
    nearest=ranked[:k]
    total=sum(v for v,_ in nearest)
    return [(name,v/total) for v,name in nearest] if total else []


def proximity_skin(ob,rig,max_influences):
    # Bone.head_local/tail_local are in armature local rest-space.
    segments=[]
    for b in rig.data.bones:
        if not b.use_deform:continue
        head=rig.matrix_world@b.head_local
        tail=rig.matrix_world@b.tail_local
        length=float((tail-head).length)
        if length>1e-5:segments.append((b.name,head,tail,length))
    if not segments:raise RuntimeError('Rig contains no usable deform bones')
    used={}
    for v in ob.data.vertices:
        wp=ob.matrix_world@v.co
        for name,value in nearest_bone_weights(wp,segments,max_influences):
            if value<=0.:continue
            group=used.get(name)
            if group is None:
                group=ob.vertex_groups.new(name=name);used[name]=group
            group.add([v.index],value,'REPLACE')
    if not weighted(ob):raise RuntimeError('Proximity skin produced no weights')
    attach_armature(ob,rig)



def smooth_new_skin_with_scipy(ob,rig,a):
    """Runs real SciPy in external CPU Python. Only newly generated groups change."""
    valid={bone.name for bone in rig.data.bones if bone.use_deform}
    assigned_groups={group.index:group.name for group in ob.vertex_groups}
    names=sorted({name for name in assigned_groups.values() if name in valid})
    if not names:
        raise RuntimeError('SciPy smoothing requires newly generated deform-bone weights')
    if len(names)>128:
        raise RuntimeError('Too many bones for conservative CPU SciPy budget')
    bone_index={name:i for i,name in enumerate(names)}
    weights=[]
    for v in ob.data.vertices:
        row=[0.0]*len(names)
        for assigned in v.groups:
            name=assigned_groups.get(assigned.group)
            if name not in bone_index:
                if assigned.weight>1e-7:raise RuntimeError('Unexpected weighted nondeform vertex group: '+str(name))
                continue
            row[bone_index[name]]=float(assigned.weight)
        weights.append(row)
    payload={'bones':names,'vertices':[list(v.co) for v in ob.data.vertices],
             'faces':[list(poly.vertices) for poly in ob.data.polygons],
             'weights':weights,'max_influences':a.max_influences,
             'iterations':a.scipy_iterations,'strength':a.scipy_strength}
    if not payload['faces']:
        raise RuntimeError('SciPy smoother needs connected mesh polygons')
    with tempfile.TemporaryDirectory(prefix='monster-scipy-') as temp:
        folder=Path(temp);inp=folder/'skin.json';out=folder/'smoothed.json'
        inp.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False),encoding='utf8')
        command=[a.scipy_python,str(Path(__file__).with_name('scipy_skin_weights.py')),
                 '--input',str(inp),'--output',str(out)]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              text=True,check=False,timeout=300)
        if result.returncode or not out.exists():
            raise RuntimeError('SciPy weight solver unavailable or rejected mesh: '+result.stderr[-700:])
        computed=json.loads(out.read_text(encoding='utf8'))
    if computed.get('bones')!=names or computed.get('vertices')!=len(ob.data.vertices):
        raise RuntimeError('SciPy result mismatch: object identity/vertex count')
    values=computed.get('weights')
    if not isinstance(values,list) or len(values)!=len(ob.data.vertices):
        raise RuntimeError('SciPy returned incomplete weight array')
    for row in values:
        if len(row)!=len(names) or any(not math.isfinite(v) or v<0 for v in row):
            raise RuntimeError('SciPy weights are not finite/nonnegative')
        if abs(sum(row)-1)>1e-5 or sum(v>1e-8 for v in row)>a.max_influences:
            raise RuntimeError('SciPy weights violate glTF normalization or influence cap')
    # This happens only on unapproved, newly generated groups, after all
    # validation has passed. Existing artist-painted meshes are skipped earlier.
    groups={group.name:group for group in ob.vertex_groups}
    for group in groups.values():
        group.remove(list(range(len(ob.data.vertices))))
    for idx,row in enumerate(values):
        for name,val in zip(names,row):
            if val>1e-8:groups[name].add([idx],float(val),'REPLACE')
    if not weighted(ob):raise RuntimeError('Unexpected empty smoothed groups')
    return {'vertices':len(values),'bones':len(names),'edges':computed['edges']}


def main():
    import bpy
    a=parse()
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()))
    rig=bpy.data.objects.get(a.rig)
    if not rig or rig.type!='ARMATURE':raise RuntimeError('Existing MONSTER_RIG armature required; create with build_monster.py first')
    stats={'blender_cpu_version':list(bpy.app.version[:3]),'rig':rig.name,
           'newly_skinned':[],'scipy_weight_smooth':[],'preserved_weighted':[],'skipped':[]}
    for ob in list(bpy.data.objects):
        if ob.type!='MESH':continue
        if not skin_eligible(ob,rig):
            stats['skipped'].append(ob.name)
            continue
        old_materials=tuple(m.name if m else '' for m in ob.data.materials)
        old_morphs=tuple(k.name for k in ob.data.shape_keys.key_blocks) if ob.data.shape_keys else ()
        old_coords=[tuple(v.co) for v in ob.data.vertices]
        ok=(a.method=='auto' and heat_skin(bpy,ob,rig))
        if not ok:proximity_skin(ob,rig,a.max_influences)
        else:attach_armature(ob,rig)
        if a.scipy_skin_smooth:
            result=smooth_new_skin_with_scipy(ob,rig,a)
            stats['scipy_weight_smooth'].append({'mesh':ob.name,**result})
        if tuple(m.name if m else '' for m in ob.data.materials)!=old_materials:
            raise RuntimeError('Materials changed during skinning')
        if (tuple(k.name for k in ob.data.shape_keys.key_blocks) if ob.data.shape_keys else ())!=old_morphs:
            raise RuntimeError('Morph names changed during skinning')
        if [tuple(v.co) for v in ob.data.vertices]!=old_coords:
            raise RuntimeError('Base mesh geometry changed during skinning')
        stats['newly_skinned'].append(ob.name)
    # Save as a new .blend; source is never overwritten.
    dest=Path(a.output_blend).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest))
    if a.output_glb:
        # Reuse existing strictly filtered export selection.
        from blender_sculpt_bridge import is_monster_mesh,save_selected_glb
        eligible=[ob for ob in bpy.data.objects if is_monster_mesh(ob,rig)]
        if not eligible:raise RuntimeError('No skinned creature meshes eligible for GLB export')
        glb=Path(a.output_glb).resolve();glb.parent.mkdir(parents=True,exist_ok=True)
        save_selected_glb(glb,rig,eligible)
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':main()
