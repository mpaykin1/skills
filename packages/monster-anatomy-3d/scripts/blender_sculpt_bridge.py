#!/usr/bin/env python3
"""BLENDER 4.5 LTS anatomical deformation stage for Monster Anatomy 3D.

Operates on the *existing* muscle meshes, not replacement cylinders.
Creates anatomically localized flex/extension shape keys and bakes their
pose-dependent values into NLA-matched morph clips, so glTF can export them.
Creates non-exported subdivision workbench duplicates for manual sculpting.
These are artistic corrective deformations, NOT finite-element muscle physics.

blender -b --python scripts/blender_sculpt_bridge.py -- \
  --blend monster_three_way_anatomy.blend \
  --output-blend monster_blender_detail.blend \
  --output-glb monster_blender_detail.glb
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
# The companion transfer script bridges artist-made Myo muscle meshes to the
# Z-Anatomy / MPFB-aligned monster skeleton.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from myo_rig_bridge import auto_attach_myo

# Bone-target map is deliberately aligned to the existing monster skeleton.
# Individual objects are named in scripts/build_monster.py. MyoGeneratorRemix
# objects marked with `monster_muscle` are also eligible after manual skinning.
TARGETS = (
    ('trapezius', 'spine', .8),
    ('scapular', 'spine', 1.0),
    ('thoracic', 'spine', .9),
    ('pectoral', 'upperarm', 1.0),
    ('deltoid', 'upperarm', 1.1),
    ('triceps', 'forearm', 1.0),
    ('biceps', 'forearm', 1.15),
    ('brachialis', 'forearm', 1.2),
    ('forearm flex', 'hand', 1.0),
    ('forearm extensor', 'hand', .6),
    ('abdominal', 'spine', .8),
    ('neck anterior', 'neck', .6),
    ('gluteus', 'thigh', 1.0),
    ('quadriceps', 'shin', 1.15),
    ('hamstring', 'shin', 1.0),
    ('calf', 'foot', 1.1),
    ('achilles', 'foot', .6),
)

NON_MUSCLE = ('hairless skull', 'prominent jaw', 'claw knuckle', 'finger ', 'elongated foot')
EXCLUDE_PREFIX = ('ZA_', 'MPFB_', 'SCULPT_', 'Z-ANATOMY_')

def is_monster_mesh(obj, rig):
    if obj.type != 'MESH': return False
    if obj.parent != rig: return False
    if obj.name.startswith(EXCLUDE_PREFIX): return False
    if obj.get('reference_only') or obj.get('non_exportable_reference'): return False
    return True

def is_muscle(obj):
    name=obj.name.lower()
    if name.startswith(tuple(x.lower() for x in EXCLUDE_PREFIX)): return False
    if name.startswith(NON_MUSCLE): return False
    return bool(obj.get('monster_muscle') or obj.get('is_myo_muscle') or
                any(part in name for part,_,_ in TARGETS))

def target_bone(obj, rig):
    name=obj.name.lower()
    canonical=name.removesuffix('_muscle')
    side=('_L' if canonical.endswith('_l') else '_R' if canonical.endswith('_r') else '')
    for alias,bone,magnitude in TARGETS:
        if alias in name:
            candidate=bone+side if bone in ('upperarm','forearm','hand','thigh','shin','foot') else bone
            if rig.pose.bones.get(candidate): return candidate,magnitude
    # For genuine addon meshes, allow a metadata-provided target rather than
    # assuming the mesh can be mapped from arbitrary upstream object names.
    if obj.get('monster_muscle') or obj.get('is_myo_muscle'):
        b=str(obj.get('flex_bone',''))
        if rig.pose.bones.get(b):return b,float(obj.get('flex_gain',.85))
    return None,None

def loft_centerline(verts, sides=12):
    # The original build_monster loft uses contiguous rings of 12 vertices.
    if len(verts) != 300: return None
    centers=[]
    for start in range(0,len(verts),sides):
        center=Vector((0,0,0))
        for v in verts[start:start+sides]:center+=v
        centers.append(center/sides)
    return centers

def deformation_coordinates(obj, flex_gain=.18, stretch_gain=.07):
    verts=[v.co.copy() for v in obj.data.vertices]
    n=len(verts)
    if n < 18: raise ValueError('Muscle mesh too small for shape keys')
    centers=loft_centerline(verts)
    if centers:
        axis=(centers[-1]-centers[0]).normalized()
        length=(centers[-1]-centers[0]).length
    else:
        lo=Vector(tuple(min(v[k] for v in verts) for k in range(3)))
        hi=Vector(tuple(max(v[k] for v in verts) for k in range(3)))
        dims=hi-lo; main=max(range(3),key=lambda k:dims[k]);length=dims[main]
        axis=Vector(tuple(1 if k==main else 0 for k in range(3)))
        middle=sum(verts,Vector((0,0,0)))/n
    if length < 1e-5:raise ValueError('Degenerate muscle centreline')
    inflated=[]; extended=[]
    for i,p in enumerate(verts):
        if centers:
            idx=i//12; t=idx/(len(centers)-1)
            center=centers[idx]
        else:
            t=max(0.,min(1.,(p[main]-lo[main])/max(1e-6,length)))
            center=middle+axis*(p-middle).dot(axis)
        envelope=max(0.0,math.sin(math.pi*t))**1.7
        radial=p-center
        # Deliberately preserve tendon tips and bone attachment endpoints.
        # A contracting belly becomes thicker and slightly shorter, an extended
        # one becomes leaner and longer; neither simply scales the whole mesh.
        inflated.append(center+radial*(1.+flex_gain*envelope)
                        +axis*(.5-t)*length*.06*envelope)
        extended.append(center+radial*(1.-stretch_gain*envelope)
                        +axis*(t-.5)*length*.035*envelope)
    return inflated,extended

def ensure_shape_keys(obj, flex_gain, stretch_gain):
    if obj.data.shape_keys and obj.data.shape_keys.key_blocks.get('ANATOMY_FLEX'):
        raise RuntimeError(obj.name+' already has ANATOMY_FLEX, refusing duplicate procedural deformation')
    flex,extend=deformation_coordinates(obj,flex_gain,stretch_gain)
    if obj.data.shape_keys is None:obj.shape_key_add(name='Basis',from_mix=False)
    flex_key=obj.shape_key_add(name='ANATOMY_FLEX',from_mix=False)
    stretch_key=obj.shape_key_add(name='ANATOMY_STRETCH',from_mix=False)
    for i,v in enumerate(flex):flex_key.data[i].co=v
    for i,v in enumerate(extend):stretch_key.data[i].co=v
    flex_key.value=0.;stretch_key.value=0.
    obj['monster_muscle']=True
    obj['shape_key_description']='Artistic flex and stretch around a stable centreline; no biological solver'
    return flex_key,stretch_key

def ensure_sculpt_collection(scene):
    collection=bpy.data.collections.get('SCULPT_WORKBENCH_NON_EXPORT')
    if not collection:
        collection=bpy.data.collections.new('SCULPT_WORKBENCH_NON_EXPORT')
        scene.collection.children.link(collection)
    return collection

def add_sculpt_copy(obj, collection):
    # High-resolution editable duplicate is hidden until the sculptor chooses it.
    # We preserve the deforming game mesh and its vertex weights unchanged.
    copy=obj.copy();copy.data=obj.data.copy()
    collection.objects.link(copy)
    copy.name='SCULPT_'+obj.name
    copy['non_exportable_reference']=True
    copy['sculpt_source_mesh']=obj.name
    for mod in list(copy.modifiers):
        if mod.type=='SUBSURF':copy.modifiers.remove(mod)
    sub=copy.modifiers.new('Blender sculpt preview subdivision','SUBSURF')
    sub.levels=2;sub.render_levels=2
    copy.hide_render=True
    copy.hide_set(True)
    return copy

def bone_angle(pb):
    return max(abs(float(pb.rotation_euler[0])),abs(float(pb.rotation_euler[1]))*.55,
               abs(float(pb.rotation_euler[2]))*.45)

def sample_rig_clips(scene,rig,muscles,step=2):
    anim=rig.animation_data
    if anim is None or not anim.nla_tracks:raise RuntimeError('Rig has no NLA strips for export')
    tracks=[track for track in anim.nla_tracks if len(track.strips)]
    previous={t.name:t.mute for t in tracks}
    source_frame=scene.frame_current
    samples={}
    try:
        for tr in tracks:
            for t in tracks:t.mute = t!=tr
            strip=tr.strips[0]
            first=max(1,int(round(strip.frame_start)))
            last=int(round(strip.frame_end))
            if last<=first or last-first>3000:raise RuntimeError('Unexpected rig clip duration: '+tr.name)
            frames=list(range(first,last+1,step))
            if frames[-1]!=last:frames.append(last)
            samples[tr.name]={obj.name:[] for obj,_,_ in muscles}
            for f in frames:
                scene.frame_set(f)
                for obj,bone,gain in muscles:
                    rotation=bone_angle(rig.pose.bones[bone])
                    val=min(1.,max(0.,rotation*gain))
                    samples[tr.name][obj.name].append((f,round(val,5)))
    finally:
        for track in tracks:track.mute=previous[track.name]
        scene.frame_set(source_frame)
    return samples

def bake_shape_key_nla(muscles, samples):
    for obj,bone,gain in muscles:
        keys=obj.data.shape_keys
        flex=keys.key_blocks['ANATOMY_FLEX']
        stretch=keys.key_blocks['ANATOMY_STRETCH']
        keys.animation_data_create()
        for clip,by_mesh in samples.items():
            action=bpy.data.actions.new('MORPH_'+clip+'_'+obj.name)
            keys.animation_data.action=action
            for frame,value in by_mesh[obj.name]:
                flex.value=value
                stretch.value=max(0.,value*.3)
                flex.keyframe_insert(data_path='value',frame=frame,group='Anatomy')
                stretch.keyframe_insert(data_path='value',frame=frame,group='Anatomy')
            # 4.5 supports NLA tracks for shape-key actions; track names group
            # related actions with MONSTER_RIG tracks on export.
            keys.animation_data.action=None
            track=keys.animation_data.nla_tracks.new()
            track.name=clip
            track.strips.new(clip,1,action)
            for curve in action.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
        flex.value=0.;stretch.value=0.

def save_selected_glb(dest,rig,meshes):
    for obj in bpy.context.selected_objects:obj.select_set(False)
    export_set=[rig]+meshes
    for obj in export_set:obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,
        export_animations=True,export_animation_mode='NLA_TRACKS',
        export_skins=True,export_morph=True,export_force_sampling=True,
        export_apply=False,export_cameras=False,export_lights=False)
    for obj in export_set:obj.select_set(False)
    if not dest.exists() or dest.stat().st_size<1000:
        raise RuntimeError('The glTF exporter failed to create a valid-size file')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--blend',required=True)
    ap.add_argument('--output-blend',required=True)
    ap.add_argument('--output-glb',required=True)
    ap.add_argument('--workbench-copies',action='store_true',default=False,
                    help='Duplicate game muscles into hidden high-resolution sculpt workbench')
    ap.add_argument('--flex-amplitude',type=float,default=.19)
    ap.add_argument('--sample-step',type=int,default=2)
    opts=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not 0<opts.flex_amplitude<=.45:ap.error('--flex-amplitude must be 0..0.45')
    if not 1<=opts.sample_step<=6:ap.error('--sample-step must be 1..6')
    bpy.ops.wm.open_mainfile(filepath=str(Path(opts.blend).resolve()))
    rig=bpy.data.objects.get('MONSTER_RIG')
    if rig is None or rig.type!='ARMATURE':raise RuntimeError('MONSTER_RIG missing')
    myo_attached=auto_attach_myo(bpy,rig)
    mesh=[obj for obj in bpy.data.objects if is_monster_mesh(obj,rig)]
    muscles=[]
    for obj in mesh:
        if not is_muscle(obj):continue
        bone,gain=target_bone(obj,rig)
        if not bone:continue
        ensure_shape_keys(obj,opts.flex_amplitude,opts.flex_amplitude*.44)
        muscles.append((obj,bone,gain))
    if len(muscles)<8:raise RuntimeError('Fewer than 8 deformable anatomy meshes; inputs may not be the intended creature')
    samples=sample_rig_clips(bpy.context.scene,rig,muscles,opts.sample_step)
    bake_shape_key_nla(muscles,samples)
    if opts.workbench_copies:
        collection=ensure_sculpt_collection(bpy.context.scene)
        for obj,_,_ in muscles:add_sculpt_copy(obj,collection)
    bpy.context.scene.frame_set(1)
    blend=Path(opts.output_blend).resolve();glb=Path(opts.output_glb).resolve()
    blend.parent.mkdir(parents=True,exist_ok=True)
    glb.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    save_selected_glb(glb,rig,mesh)
    print(json.dumps({'scene':str(blend),'glb':str(glb),'muscles_morph_baked':len(muscles),'myo_muscles_auto_skinned':len(myo_attached),
                      'clips':list(samples),'game_meshes_exported':len(mesh)},ensure_ascii=False))

if __name__=='__main__':main()
