#!/usr/bin/env python3
"""Create Blender Studio Pose Shape Keys authoring hooks for existing monster muscles.

Real addon registration and real RNA pose_keys are required. This deliberately
creates an authoring .blend (not fabricated sculpt corrections): output geometry,
rig, original morphs, actions and NLA clips remain untouched. Corrective sculpt
work is an authoring step and game exports must bake finished keys to animation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--addon-dir',required=True,help='Directory containing pose_shape_keys package')
    p.add_argument('--track',default='ATTACK')
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def signature(ob):
    h=hashlib.sha256()
    h.update(str(len(ob.data.vertices)).encode());h.update(str(len(ob.data.polygons)).encode())
    for v in ob.data.vertices:
        for c in v.co:h.update(float(c).hex().encode())
        for grp in v.groups:h.update((str(grp.group)+':'+float(grp.weight).hex()).encode())
    for p in ob.data.polygons:
        h.update((','.join(str(v) for v in p.vertices)+':'+str(p.material_index)).encode())
    for key in (ob.data.shape_keys.key_blocks if ob.data.shape_keys else []):
        h.update(key.name.encode())
        for v in key.data:
            for c in v.co:h.update(float(c).hex().encode())
    for m in ob.data.materials:h.update((m.name if m else 'none').encode())
    for uv in ob.data.uv_layers:
        for d in uv.data:
            for c in d.uv:h.update(float(c).hex().encode())
    return h.hexdigest()


def select_only(bpy, ob):
    if bpy.context.object is not None and bpy.context.object.mode!='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for item in bpy.context.selected_objects:item.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active=ob


def source_clip(rig,name):
    if not rig.animation_data or not rig.animation_data.nla_tracks:
        raise RuntimeError('Original monster rig has no NLA animation clips')
    tracks=[t for t in rig.animation_data.nla_tracks if t.strips and t.name.upper()==name.upper()]
    if len(tracks)!=1:raise RuntimeError('Exactly one original NLA track '+name+' is required')
    track=tracks[0]
    if len(track.strips)!=1:raise RuntimeError('Only one strip per source track supported')
    return track,track.strips[0]


def create_pose_key(obj, action, frame, target):
    pose_keys=obj.data.pose_keys
    name='MONSTER_PSK_'+target
    if any(p.name==name for p in pose_keys):
        raise RuntimeError('Duplicate Pose Shape Key: '+obj.name+':'+name)
    pk=pose_keys.add()
    pk.name=name
    pk.action=action
    pk.frame=int(frame)
    if hasattr(obj.data,'active_pose_key_index'):
        obj.data.active_pose_key_index=len(pose_keys)-1
    if not hasattr(pk,'target_shapes'):
        raise RuntimeError('Official Pose Shape Keys API changed: missing target_shapes')
    t=pk.target_shapes.add()
    if hasattr(t,'shape_key_name'):t.shape_key_name=target
    if hasattr(t,'name'):t.name=target
    if hasattr(t,'vertex_group'):t.vertex_group=''
    if not any(k.name==target for k in obj.data.shape_keys.key_blocks):
        raise RuntimeError('Target shape key disappeared during Pose Key setup')
    return name


def best_frame(bpy,rig,bone,track,strip):
    # Action is evaluated through the existing NLA track; keep original mix/mute state.
    from blender_sculpt_bridge import bone_angle
    first=max(1,int(strip.frame_start));last=int(strip.frame_end)
    if last-first>1000 or last<=first:raise RuntimeError('Invalid NLA clip duration')
    best=(first,-1.0)
    for frame in sorted(set([first,last]+list(range(first,last+1,max(1,(last-first)//14))))):
        bpy.context.scene.frame_set(frame)
        pb=rig.pose.bones.get(bone)
        if pb is None:continue
        val=bone_angle(pb)
        if val>best[1]:best=(frame,val)
    if best[1]<0:raise RuntimeError('Cannot evaluate '+bone)
    # NLA is linear when strip.repeat==1; any other case needs explicit support.
    if abs(strip.repeat-1.0)>1e-6:raise RuntimeError('Repeated NLA strips are unsupported for pose-key registration')
    action_frame=float(strip.action_frame_start)+(best[0]-float(strip.frame_start))/max(.0001,float(strip.scale))
    return int(round(max(float(strip.action_frame_start),min(float(strip.action_frame_end),action_frame))))


def main():
    import bpy
    from blender_sculpt_bridge import is_monster_mesh,target_bone
    a=parse_args()
    source=Path(a.blend).expanduser().resolve();out=Path(a.output_blend).expanduser().resolve()
    if not source.is_file() or source.suffix.lower()!='.blend':raise RuntimeError('Input BLEND missing')
    if out==source or out.suffix.lower()!='.blend':raise RuntimeError('Output must be distinct .blend')
    if out.exists():raise RuntimeError('Output exists, refusing overwrite: '+str(out))
    if tuple(bpy.app.version[:2])<(4,2) or tuple(bpy.app.version[:2])>=(5,0):
        raise RuntimeError('Pose Shape Keys 1.0.0 requires Blender 4.2 through 4.5')
    addon=Path(a.addon_dir).expanduser().resolve()
    if not (addon/'pose_shape_keys'/'blender_manifest.toml').is_file():
        raise RuntimeError('Pose Shape Keys 1.0.0 is not installed in '+str(addon))
    sys.path.insert(0,str(addon))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig=bpy.data.objects.get('MONSTER_RIG')
    if not rig or rig.type!='ARMATURE':raise RuntimeError('MONSTER_RIG not found')
    meshes=[o for o in bpy.data.objects if is_monster_mesh(o,rig) and
            o.data.shape_keys and o.data.shape_keys.key_blocks.get('ANATOMY_FLEX') and
            o.data.shape_keys.key_blocks.get('ANATOMY_STRETCH')]
    if not meshes:raise RuntimeError('No muscle shape keys: run Blender sculpt stage before Pose Shape Keys')
    before={ob.name:signature(ob) for ob in meshes}
    bone_names={b.name for b in rig.data.bones}
    old_actions={a.name for a in bpy.data.actions}
    old_tracks={t.name for t in rig.animation_data.nla_tracks} if rig.animation_data else set()
    import pose_shape_keys
    if not hasattr(bpy.types.Mesh,'pose_keys'):
        pose_shape_keys.register()
    if not hasattr(bpy.types.Mesh,'pose_keys'):
        raise RuntimeError('Pose Shape Keys addon did not register Mesh.pose_keys')
    track,strip=source_clip(rig,a.track)
    all_tracks=list(rig.animation_data.nla_tracks)
    prior_mutes={t.name:t.mute for t in all_tracks}
    start=bpy.context.scene.frame_current
    mapping=[]
    try:
        for t in all_tracks:t.mute=(t!=track)
        # Build only metadata. Sculpting is performed on stored evaluated mesh by artist,
        # then Pose Shape Keys pushes that changed shape to existing shape keys.
        frame_by_bone={}
        for obj in meshes:
            bone,_gain=target_bone(obj,rig)
            if not bone or bone not in rig.pose.bones:continue
            if bone not in frame_by_bone:
                frame_by_bone[bone]=best_frame(bpy,rig,bone,track,strip)
            frame=frame_by_bone[bone]
            pk=create_pose_key(obj,strip.action,frame,'ANATOMY_FLEX')
            mapping.append({'mesh':obj.name,'bone':bone,'action':strip.action.name,'frame':frame,'pose_key':pk,'target':'ANATOMY_FLEX'})
    finally:
        for t in all_tracks:t.mute=prior_mutes[t.name]
        bpy.context.scene.frame_set(start)
    if not mapping:raise RuntimeError('No muscle meshes with identifiable flex bones')
    if {o.name:signature(o) for o in meshes}!=before:
        raise RuntimeError('Pose Shape Key registration changed source geometry/materials/weights/morphs')
    if {b.name for b in rig.data.bones}!=bone_names or old_actions!={ac.name for ac in bpy.data.actions}:
        raise RuntimeError('Pose Shape Key stage changed skeleton or action library')
    if old_tracks!={t.name for t in rig.animation_data.nla_tracks}:
        raise RuntimeError('Pose Shape Key stage changed original NLA clips')
    out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    idx=out.with_name(out.stem+'_pose_keys.json')
    idx.write_text(json.dumps({'source_blend':str(source),'authoring_blend':str(out),
        'addon':'Blender Studio Pose Shape Keys 1.0.0','correctives_sculpted':False,
        'pose_keys':mapping},ensure_ascii=False,indent=2),encoding='utf8')
    print('POSE SHAPE KEYS authoring project:',out)
    print('POSE KEYS CREATED:',len(mapping))
    print('SCULPT NOT PERFORMED. The resulting .blend requires intentional sculpt and push.')

if __name__=='__main__':main()
