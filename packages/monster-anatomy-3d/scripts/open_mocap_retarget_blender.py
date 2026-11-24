#!/usr/bin/env python3
"""Retarget real Open Mocap 40-landmark motion to SAME Monster Anatomy 3D rig.

CPU Blender 4.5+; single existing MONSTER_RIG, unchanged skin, anatomy, UV,
muscle shape geometry and old clips. Export new NLA clip and synchronize muscle
flex using original Rigger bridge's baked-morph sampling helper. This is an
approximate upper/lower limb directional retarget, not full-body IK or physical
motion reconstruction; feet, finger articulation and world root are not tracked.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))

# Open Mocap / MediaPipe 33 original joints + 7 derived centroids:
# 33 hips center, 34 shoulder center, 35 right hand center,
# 36 left hand center, 37 ears center, 38 mouth center, 39 eyes center.
DEFAULT_PAIRS={
  'spine':(33,34),'neck':(34,37), 'head':(37,39),
  'upperarm_L':(11,13),'forearm_L':(13,15),'hand_L':(15,19),
  'upperarm_R':(12,14),'forearm_R':(14,16),'hand_R':(16,20),
  'thigh_L':(23,25),'shin_L':(25,27),'foot_L':(27,31),
  'thigh_R':(24,26),'shin_R':(26,28),'foot_R':(28,32),
}


def args():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--landmarks',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--output-glb',required=True)
    p.add_argument('--bone-map',default='')
    p.add_argument('--clip',default='MOCAP_WALK')
    p.add_argument('--mirror',action='store_true')
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def parse_landmarks(path):
    data=json.loads(Path(path).read_text(encoding='utf8'))
    if data.get('format')!='monster-open-mocap-cpu-v1' or data.get('points')!=40:
        raise ValueError('Expected authentic Open Mocap CPU v1 frame data')
    fps=float(data.get('fps',0))
    frames=data.get('landmarks')
    if not 1<=fps<=240 or not isinstance(frames,list) or not 2<=len(frames)<=2400:
        raise ValueError('Invalid source FPS or frame count')
    for idx,frame in enumerate(frames):
        if not isinstance(frame,list) or len(frame)!=120 or not all(type(x) in (int,float) and math.isfinite(x) for x in frame):
            raise ValueError('Bad landmark frame '+str(idx))
    return fps,frames


def bone_map(rig,file):
    if file:
        loaded=json.loads(Path(file).read_text(encoding='utf8'))
        if not isinstance(loaded,dict) or len(loaded)<3:
            raise ValueError('Provide >=3 bone-name:[landmark_index_1,landmark_index_2] mapping pairs')
        mapped={}
        for name,indices in loaded.items():
            if name not in rig.pose.bones:
                raise ValueError('Bone not in existing monster rig: '+str(name))
            if not isinstance(indices,list) or len(indices)!=2 or not all(type(i)==int and 0<=i<40 for i in indices) or indices[0]==indices[1]:
                raise ValueError('Bad landmark index pair for '+str(name))
            mapped[name]=tuple(indices)
    else:
        mapped={name:points for name,points in DEFAULT_PAIRS.items() if name in rig.pose.bones}
    if len(mapped)<6:
        raise ValueError('Insufficient verified monster bone names. Supply explicit --bone-map')
    return mapped


def vec(frame,idx,V,mirror=False):
    x,y,z=frame[3*idx:3*idx+3]
    # Open Mocap image x = our rig lateral Y, image vertical = rig Z,
    # MediaPipe approximate depth = rig forward X. Monster rig uses local X forward.
    return V((z, x if mirror else -x, -y))


def interpolate(frames,old_fps,new_fps):
    duration=(len(frames)-1)/old_fps
    total=round(duration*new_fps)+1
    if total>2400:raise ValueError('Mocap clip exceeds 2400 Blender frames')
    for i in range(total):
        pos=min(len(frames)-1,i*old_fps/new_fps)
        a=math.floor(pos);b=min(a+1,len(frames)-1);t=pos-a
        if a==b:yield frames[a]
        else:yield [v*(1-t)+w*t for v,w in zip(frames[a],frames[b])]


def smooth_joints(frames,alpha=.38):
    prev=frames[0][:]
    yield prev
    for raw in frames[1:]:
        prev=[a+(b-a)*alpha for a,b in zip(prev,raw)]
        yield prev


def depth(pb):
    result=0
    while pb.parent:
        result+=1;pb=pb.parent
    return result


def main():
    import bpy
    from mathutils import Matrix,Vector
    if tuple(bpy.app.version[:2])<(4,5):
        raise RuntimeError('This retargeter requires Blender 4.5+, no GPU')
    a=args()
    inp=Path(a.blend).expanduser().resolve()
    raw=Path(a.landmarks).expanduser().resolve()
    out=Path(a.output_blend).expanduser().resolve()
    glb=Path(a.output_glb).expanduser().resolve()
    if not inp.is_file() or not raw.is_file():raise FileNotFoundError('Missing input BLEND or motion data')
    if inp.suffix.lower()!='.blend' or out.suffix.lower()!='.blend' or glb.suffix.lower()!='.glb':
        raise ValueError('Expected input .blend, output .blend and .glb')
    if len({inp,out,glb,raw})!=4 or out.exists() or glb.exists():
        raise ValueError('Output paths must be distinct and must not exist')
    if not re.fullmatch('[A-Za-z0-9_-]{1,55}',a.clip):
        raise ValueError('Clip name must be A-Z / 0-9 / underscore / hyphen')
    fps,tracked=parse_landmarks(raw)
    bpy.ops.wm.open_mainfile(filepath=str(inp))
    rig=bpy.data.objects.get('MONSTER_RIG')
    if not rig or rig.type!='ARMATURE':raise RuntimeError('Original MONSTER_RIG missing')
    from rigger_monster_blender import (selected_game_meshes,capture,assert_preserved,
                                       bake_new_muscle_clip,export_game_glb)
    meshes=selected_game_meshes(bpy,rig)
    prior=capture(bpy,rig,meshes)
    if a.clip in prior['nla'] or a.clip in prior['actions']:
        raise ValueError('Clip already exists; refusing to replace existing motion')
    mapping=bone_map(rig,a.bone_map)
    ordered=sorted(mapping,key=lambda n:depth(rig.pose.bones[n]))
    scene=bpy.context.scene
    frames=list(smooth_joints(list(interpolate(tracked,fps,scene.render.fps))))
    if len(frames)<2:raise ValueError('Insufficient captured motion')
    # Preserve existing NLA and source actions in the scene, separate from our new clip.
    rig.animation_data_create()
    anim=rig.animation_data
    current_action=anim.action
    original_mutes={t.name:t.mute for t in anim.nla_tracks}
    saved_frame=scene.frame_current
    for track in anim.nla_tracks:track.mute=True
    anim.action=None
    baseline={}
    for name,(u,v) in mapping.items():
        direction=vec(frames[0],v,Vector,a.mirror)-vec(frames[0],u,Vector,a.mirror)
        if direction.length<1e-7:raise ValueError('Degenerate pose baseline: '+name)
        baseline[name]=direction.normalized()
    clip_action=bpy.data.actions.new(a.clip)
    anim.action=clip_action
    # Never change rotation mode of existing bones: original Euler actions must keep working.
    modes={name:rig.pose.bones[name].rotation_mode for name in mapping}
    try:
        for frame_num,frame in enumerate(frames,1):
            scene.frame_set(frame_num)
            # Start from rest pose. Unmapped bones remain untouched by the new clip.
            for pb in rig.pose.bones:pb.matrix_basis.identity()
            for name in ordered:
                u,v=mapping[name]
                current=vec(frame,v,Vector,a.mirror)-vec(frame,u,Vector,a.mirror)
                if current.length<1e-7:continue
                quat=baseline[name].rotation_difference(current.normalized())
                bone=rig.pose.bones[name]
                rest=bone.bone.matrix_local
                pivot=bone.bone.head_local
                desired=Matrix.Translation(pivot)@quat.to_matrix().to_4x4()@Matrix.Translation(-pivot)@rest
                bone.matrix=desired
                channel={'QUATERNION':'rotation_quaternion','AXIS_ANGLE':'rotation_axis_angle'}.get(modes[name],'rotation_euler')
                bone.keyframe_insert(data_path=channel,frame=frame_num,group=name)
    finally:
        anim.action=None
        for name,mode in modes.items():rig.pose.bones[name].rotation_mode=mode
        for track in anim.nla_tracks:track.mute=original_mutes[track.name]
        scene.frame_set(saved_frame)
    if clip_action.frame_range[1]<=clip_action.frame_range[0]:
        raise RuntimeError('New mocap Action has no effective frame range')
    track=anim.nla_tracks.new();track.name=a.clip
    track.strips.new(a.clip,1,clip_action)
    assert_preserved(bpy,rig,meshes,prior)
    # Rigger's existing anatomical morph helper computes flex/stretch of muscle
    # after retarget: reuse the same real MUSCLE shape-key NLA workflow.
    morphed=bake_new_muscle_clip(bpy,rig,meshes,a.clip)
    assert_preserved(bpy,rig,meshes,prior)
    out.parent.mkdir(parents=True,exist_ok=True)
    glb.parent.mkdir(parents=True,exist_ok=True)
    # Blender source retains every pre-existing Action, NLA and original mesh.
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    # Export only original rig and its original hero meshes, not anatomy donors.
    export_game_glb(bpy,rig,meshes,glb,prior['nla']|{a.clip})
    print('Open Mocap CPU retarget:',len(frames),'frames;',len(mapping),'bones;',morphed,'muscle morphs; new GLB',glb)

if __name__=='__main__':main()
