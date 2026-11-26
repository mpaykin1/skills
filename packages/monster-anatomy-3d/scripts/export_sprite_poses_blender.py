#!/usr/bin/env python3
"""Blender 4.5+: export the SAME MONSTER_RIG's actual deformed pose meshes as OBJs.

For --clip ALL, discover real named bone actions (no generated fake movement) and
export each one in its own subdirectory with a shared source coordinate system.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import sys


def argv():
    items=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blend',required=True);p.add_argument('--output',required=True)
    p.add_argument('--clip',default='ALL')
    p.add_argument('--frames',type=int,default=12)
    p.add_argument('--rig',default='MONSTER_RIG')
    return p.parse_args(items)


def bone_action(action):
    # Blender 4.5 layered/slotted Action API can differ. Prefer known authored
    # names; never try shape-key-only actions as rig animations.
    up=action.name.upper()
    if up in {'IDLE_BREATH','STALK_LOOP','GRAB_ATTACK'} or up.startswith(('MOCAP_','RIGGER_')):
        return True
    try:
        return any('pose.bones[' in curve.data_path for curve in action.fcurves)
    except (AttributeError,TypeError):return False


def main():
    import bpy
    args=argv()
    if not 2<=args.frames<=48:raise ValueError('Pose frame count must be 2..48')
    src=Path(args.blend).expanduser().resolve()
    dest=Path(args.output).expanduser().resolve()
    if dest.exists():raise FileExistsError(f'Export destination exists, source never overwritten: {dest}')
    if not src.is_file() or src.suffix.lower()!='.blend':raise FileNotFoundError('Existing Blender .blend required')
    bpy.ops.wm.open_mainfile(filepath=str(src))
    rig=bpy.data.objects.get(args.rig)
    if rig is None or rig.type!='ARMATURE':raise ValueError(f'Armature {args.rig} missing')
    if args.clip.lower()=='all':
        actions=[act for act in bpy.data.actions if bone_action(act)]
    else:
        act=bpy.data.actions.get(args.clip)
        if act is None or not bone_action(act):raise ValueError(f'Rig Action {args.clip} not found')
        actions=[act]
    if not actions:raise ValueError('No real rig Actions available to bake')
    if rig.animation_data is None:rig.animation_data_create()
    animation=rig.animation_data
    bad_tokens=('NON_EXPORT','WORKBENCH','Z_ANATOMY','ZA_','MPFB','TRELLIS_REFERENCE','DONOR','GUIDE','RIGGER_CTRL','HYBRID_3D_','HYBRID_ATTACHMENTS','COLLIDER_','SHADOW_PROXY_')
    candidates=[]
    for obj in bpy.data.objects:
        if obj.type!='MESH' or obj.hide_render:continue
        col_names=[c.name.upper() for c in obj.users_collection]
        if any(any(token in s for token in bad_tokens) for s in [obj.name.upper(),*col_names]):continue
        if len(obj.data.polygons)==0:continue
        candidates.append(obj)
    if not candidates:raise ValueError('No creature game meshes to bake')
    dest.mkdir(parents=True)
    outputs={}
    duration_frames={}
    scene=bpy.context.scene
    for action in actions:
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}',action.name):
            raise ValueError('Clip must have safe path name: '+action.name)
        animation.action=action
        animation.use_nla=False
        begin,end=map(float,action.frame_range)
        if end-begin<2:raise ValueError('Action range too short: '+action.name)
        clipdir=dest/action.name;clipdir.mkdir()
        duration_frames[action.name]=end-begin
        frames=[]
        for i in range(args.frames):
            frame=begin+(end-begin)*i/args.frames
            scene.frame_set(int(frame),subframe=frame-int(frame))
            bpy.context.view_layer.update()
            bpy.ops.object.select_all(action='DESELECT')
            for obj in candidates:
                obj.hide_set(False)
                obj.select_set(True)
            bpy.context.view_layer.objects.active=candidates[0]
            path=clipdir/f'{i:03d}.obj'
            bpy.ops.wm.obj_export(filepath=str(path),export_selected_objects=True,
                                  apply_modifiers=True,export_materials=True,
                                  export_uv=True,export_normals=True)
            if not path.is_file() or path.stat().st_size<150:
                raise RuntimeError('Actual evaluated Blender pose mesh missing: '+str(path))
            frames.append({'frame':round(frame,4),'obj':path.name,'bytes':path.stat().st_size})
        outputs[action.name]=frames
        print('[sprite stacking] posed clip:',action.name,'frames:',len(frames))
    (dest/'poses.json').write_text(json.dumps({'source_blend':str(src),'clips':outputs,
                           'mesh_names':[o.name for o in candidates],
                           'durations_frames':duration_frames,
                           'source_fps':scene.render.fps/scene.render.fps_base,
                           'origin':'Blender evaluated posed geometry'},indent=2),encoding='utf8')

if __name__=='__main__':main()
