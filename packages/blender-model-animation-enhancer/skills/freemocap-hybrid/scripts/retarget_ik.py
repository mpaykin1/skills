"""Blender 4.5+ only: explicit approved Rigify IK control location targets. Rotations remain authored."""
import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);c=json.loads(a.config.read_text());raw=a.capture.read_bytes();d=json.loads(raw)
def need(v,msg):
    if not v:raise ValueError(msg)
source=Path(bpy.data.filepath);need(source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==c['source_sha256'],'source mismatch');need(hashlib.sha256(raw).hexdigest()==c['targets_sha256'] and d['hero_id']==c['hero_id'] and d['schema']=='freemocap-control-targets-v1','capture mismatch');need(c['ik_mode_reviewed'] is True,'IK mode and mapping require review');need(not a.out.exists() and a.out.suffix=='.blend','new output only')
rig=bpy.data.objects[c['rig']];need(rig.type=='ARMATURE' and any(b.name.startswith('DEF-') for b in rig.data.bones),'Rigify rig required')
scene=bpy.context.scene;fps=scene.render.fps/scene.render.fps_base;need(abs(fps-d['fps'])<.001,'match capture and Blender FPS explicitly')
ad=rig.animation_data_create();need(not any(not t.mute for t in ad.nla_tracks),'mute existing NLA for isolated retarget');need(not bpy.data.actions.get(c['action']),'new action name required')
map_=c['controls'];need({'hip','left_ankle','right_ankle','left_wrist','right_wrist'}<=set(map_) and len(set(map_.values()))==len(map_),'explicit distinct IK control names required')
for name in map_.values():
    b=rig.pose.bones[name];need(not b.bone.use_deform and not name.startswith(('DEF-','ORG-','MCH-')) and not any(b.lock_location),'only unlocked IK control locations')
scene.frame_set(c['reference_frame']);bpy.context.view_layer.update();first=d['frames'][0]['targets'];unit=scene.unit_settings.scale_length or 1.0;scale=float(c['capture_to_character_scale']);need(math.isfinite(scale) and .25<=scale<=4,'invalid scale')
# Baseline pose defines per-control offsets; world-space deltas are in calibrated Blender axes.
base={k:rig.matrix_world@rig.pose.bones[n].head for k,n in map_.items()}; matrices={k:rig.pose.bones[n].matrix.copy() for k,n in map_.items()};loc={k:rig.pose.bones[n].location.copy() for k,n in map_.items()};ad.action=None;act=bpy.data.actions.new(c['action']);ad.action=act
# Parent depth order makes target placement deterministic.
def depth(b):
    n=0
    while b.parent:b=b.parent;n+=1
    return n
order=sorted(map_,key=lambda k:depth(rig.pose.bones[map_[k]]));inv=rig.matrix_world.inverted();start=int(c['start_frame']);root_mode=c['root_mode'];need(root_mode in ('world','in_place'),'root mode required')
for sample in d['frames']:
    f=start+sample['frame'];scene.frame_set(f); targets=sample['targets'];root=Vector(targets['hip'])-Vector(first['hip']);root.z=0
    for k in order:
        pb=rig.pose.bones[map_[k]];pb.location=loc[k];bpy.context.view_layer.update();delta=Vector(targets[k])-Vector(first[k]);
        if root_mode=='in_place':delta-=root
        goal=inv@(base[k]+delta*(scale/unit));mat=pb.matrix.copy();mat.translation=goal;pb.matrix=mat;bpy.context.view_layer.update();pb.keyframe_insert(data_path='location',frame=f,group=pb.name)
        need((rig.matrix_world@pb.head-(base[k]+delta*(scale/unit))).length*unit<=.03,'IK control cannot attain target; review constraints')
scene.frame_start=start;scene.frame_end=start+len(d['frames'])-1;bpy.ops.wm.save_as_mainfile(filepath=str(a.out.resolve()));print('IK target action only; rotations, pole directions, contacts, sword, final approval and full pose export remain required')
