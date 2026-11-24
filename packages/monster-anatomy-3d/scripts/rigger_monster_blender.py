#!/usr/bin/env python3
"""Actual upstream asu37/Rigger API integration for Monster Anatomy 3D.

Preserves the original skeleton and deforming anatomical mesh. Uses Rigger
Quick Rig in PRESERVE mode, or Rigger Retargeter with source motion. New rigged
motion can drive the existing ANATOMY_FLEX/STRETCH shape-key system; it is NOT
muscle simulation. Requires an external, pinned upstream Rigger checkout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

# Blender does not guarantee its --python directory is on sys.path.
sys.path.insert(0,str(Path(__file__).resolve().parent))


def args():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',required=True,choices=('controls','retarget','export'))
    p.add_argument('--blend',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--rigger-dir',required=True)
    p.add_argument('--motion',default='')
    p.add_argument('--motion-rig',default='')
    p.add_argument('--motion-action',default='')
    p.add_argument('--bone-map',default='')
    p.add_argument('--clip',default='RIGGER_NEW_ACTION')
    p.add_argument('--in-place',action='store_true')
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def glb_descriptor(path):
    with open(path,'rb') as f:
        header=f.read(12)
        if len(header)!=12:raise RuntimeError('Incomplete GLB')
        magic,version,total=struct.unpack('<III',header)
        if magic!=0x46546c67 or version!=2 or total!=Path(path).stat().st_size:
            raise RuntimeError('Invalid GLB header')
        size,typ=struct.unpack('<II',f.read(8))
        if typ!=0x4e4f534a or size>25_000_000:raise RuntimeError('Invalid GLB JSON')
        return json.loads(f.read(size).decode('utf8'))


def clip_names(data):
    return {a.get('name') for a in data.get('animations',[]) if a.get('name')}


def mesh_signature(ob):
    """Hash geometry, skin group values, shape keys and material identifiers.
    Animation should affect the scene but must not rewrite the source meshes.
    """
    h=hashlib.sha256()
    h.update(ob.name.encode())
    for v in ob.data.vertices:
        h.update(struct.pack('<3d',*v.co))
        for grp in v.groups:
            h.update(struct.pack('<Id',grp.group,grp.weight))
    for poly in ob.data.polygons:
        h.update(struct.pack('<II',len(poly.vertices),poly.material_index))
        for idx in poly.vertices:h.update(struct.pack('<I',idx))
    for uv in ob.data.uv_layers:
        h.update(uv.name.encode());
        for u in uv.data:h.update(struct.pack('<2d',*u.uv))
    keys=ob.data.shape_keys
    if keys:
        for key in keys.key_blocks:
            h.update(key.name.encode());
            for v in key.data:h.update(struct.pack('<3d',*v.co))
    for mat in ob.data.materials:h.update((mat.name if mat else 'NONE').encode())
    for grp in ob.vertex_groups:h.update(grp.name.encode())
    return h.hexdigest()


def selected_game_meshes(bpy,rig):
    from blender_sculpt_bridge import is_monster_mesh
    meshes=[ob for ob in bpy.data.objects if is_monster_mesh(ob,rig)
             and ob.vertex_groups
             and any(m.type=='ARMATURE' and m.object==rig for m in ob.modifiers)]
    if len(meshes)<8:raise RuntimeError('Expected >=8 rigged monster anatomy meshes; cannot replace model')
    return meshes


def capture(bpy,rig,meshes):
    return dict(bones=tuple(sorted(b.name for b in rig.data.bones)),
                meshes={ob.name:mesh_signature(ob) for ob in meshes},
                actions={a.name for a in bpy.data.actions},
                nla={t.name for t in rig.animation_data.nla_tracks} if rig.animation_data else set())


def assert_preserved(bpy,rig,meshes,prior):
    now=capture(bpy,rig,meshes)
    if now['bones']!=prior['bones']:raise RuntimeError('Rigger changed original game skeleton; blocked')
    if now['meshes']!=prior['meshes']:raise RuntimeError('Rigger changed geometry, UV, morphs, skin weights or materials; blocked')
    if not prior['actions'].issubset(now['actions']):raise RuntimeError('Rigger deleted existing animation data; blocked')
    if not prior['nla'].issubset(now['nla']):raise RuntimeError('Rigger deleted original NLA tracks; blocked')


def use_object(bpy,obj):
    if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    for item in bpy.context.selected_objects:item.select_set(False)
    obj.hide_set(False)
    obj.select_set(True);bpy.context.view_layer.objects.active=obj


def create_controls(bpy,rig,meshes,prior):
    from rigger import quick_rig
    settings=bpy.context.scene.rigger_quick
    settings.armature=rig
    settings.mode='PRESERVE'
    settings.delete_source=False
    settings.hide_base=False
    settings.bake=bool(rig.animation_data and rig.animation_data.action)
    settings.twist=0
    settings.secondary=False
    use_object(bpy,rig)
    count=quick_rig.fill_limbs(settings)
    if count<1:raise RuntimeError('Cannot infer creature limb chains; Rigger manual reference setup required')
    result=quick_rig.quick_rig(bpy.context,settings)
    if not isinstance(result,tuple) or len(result)!=2 or result[0] is None:
        raise RuntimeError('Rigger did not create a valid control rig')
    assert_preserved(bpy,rig,meshes,prior)
    return result[0]


def source_action(bpy,source,before_names,chosen):
    new={a.name for a in bpy.data.actions}-before_names
    if chosen:
        if chosen not in new:raise RuntimeError('Missing animation action in imported motion: '+chosen)
        action=bpy.data.actions[chosen]
    elif len(new)==1:action=bpy.data.actions[next(iter(new))]
    elif source.animation_data and source.animation_data.action and not new:
        action=source.animation_data.action
    else:raise RuntimeError('Multiple source clips: choose --motion-action explicitly')
    if not source.animation_data:source.animation_data_create()
    source.animation_data.action=action
    return action


def bake_new_muscle_clip(bpy,rig,meshes,clip):
    """Synchronize retargeted rig motion with already existing muscle shape keys."""
    from blender_sculpt_bridge import target_bone,bone_angle,bake_shape_key_nla
    eligible=[]
    for ob in meshes:
        keys=ob.data.shape_keys
        if not keys or not all(keys.key_blocks.get(k) for k in ('ANATOMY_FLEX','ANATOMY_STRETCH')):continue
        bone,gain=target_bone(ob,rig)
        if bone:eligible.append((ob,bone,gain))
    if not eligible:return 0
    animation=rig.animation_data
    tracks=list(animation.nla_tracks)
    new_track=next((tr for tr in tracks if tr.name==clip),None)
    if new_track is None:raise RuntimeError('New retarget NLA track not found')
    original_mutes={tr.name:tr.mute for tr in tracks};frame0=bpy.context.scene.frame_current
    strip=new_track.strips[0];start=int(round(strip.frame_start));end=int(round(strip.frame_end))
    if end-start>2400 or end<=start:raise RuntimeError('Retarget clip has invalid duration')
    result={clip:{ob.name:[] for ob,_,_ in eligible}}
    try:
        for tr in tracks:tr.mute=(tr.name!=clip)
        for frame in range(start,end+1,2):
            bpy.context.scene.frame_set(frame)
            for ob,bone,gain in eligible:
                value=max(0.,min(1.,bone_angle(rig.pose.bones[bone])*gain))
                result[clip][ob.name].append((frame,round(value,5)))
        if result[clip][eligible[0][0].name][-1][0]!=end:
            bpy.context.scene.frame_set(end)
            for ob,bone,gain in eligible:
                value=max(0.,min(1.,bone_angle(rig.pose.bones[bone])*gain))
                result[clip][ob.name].append((end,round(value,5)))
    finally:
        for tr in tracks:tr.mute=original_mutes[tr.name]
        bpy.context.scene.frame_set(frame0)
    bake_shape_key_nla(eligible,result)
    return len(eligible)


def retarget_motion(bpy,rig,meshes,prior,a):
    if a.clip in prior['nla'] or a.clip in prior['actions'] or not re.fullmatch('[a-zA-Z0-9_-]{1,55}',a.clip):
        raise RuntimeError('Retarget clip must be a new simple animation name')
    before=set(bpy.data.objects); old_names={ac.name for ac in bpy.data.actions}
    path=Path(a.motion).resolve()
    if path.suffix.lower()=='.glb':bpy.ops.import_scene.gltf(filepath=str(path))
    elif path.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(path))
    else:raise RuntimeError('Only motion GLB/FBX supported')
    imported=set(bpy.data.objects)-before
    rigs=[ob for ob in imported if ob.type=='ARMATURE' and (not a.motion_rig or ob.name==a.motion_rig)]
    if len(rigs)!=1:raise RuntimeError('Motion must have exactly one armature; use --motion-rig')
    source=rigs[0]
    src_action=source_action(bpy,source,old_names,a.motion_action)
    from rigger import retarget
    settings=bpy.context.scene.rigger_remap
    settings.source=source;settings.target=rig
    settings.multiple=False;settings.action_name=a.clip
    settings.in_place=a.in_place;settings.legs_ik=False;settings.arms_ik=False
    settings.root_motion=False
    if a.bone_map:
        mapping=json.loads(Path(a.bone_map).read_text(encoding='utf8'))
        if not isinstance(mapping,dict) or len(mapping)<3:raise RuntimeError('Explicit source-to-monster bone JSON needs 3+ pairs')
        settings.items.clear()
        for src,dest in mapping.items():
            if src not in source.pose.bones or dest not in rig.pose.bones:
                raise RuntimeError(f'Unmatched source-to-target bone: {src} => {dest}')
            item=settings.items.add();item.source=src;item.target=dest
            item.location=bool(re.search('root|pelvis|hip',dest,re.I))
    elif retarget.auto_map(settings)<3:
        raise RuntimeError('Rigger could not match 3 bones; supply an explicit --bone-map')
    use_object(bpy,rig)
    action=retarget.retarget(bpy.context,settings)
    if action is None or action.name!=a.clip:
        raise RuntimeError('Rigger did not produce the expected new motion clip')
    # New clip gets its OWN track: the original IDLE/STALK/ATTACK tracks stay.
    rig.animation_data_create()
    rig.animation_data.action=None
    track=rig.animation_data.nla_tracks.new()
    track.name=a.clip
    start=int(round(action.frame_range[0]));end=int(round(action.frame_range[1]))
    track.strips.new(a.clip,max(1,start),action)
    # Never export the imported source person or its animation/geometry.
    for ob in imported:bpy.data.objects.remove(ob,do_unlink=True)
    for name in ({ac.name for ac in bpy.data.actions}-old_names)-{action.name}:
        act=bpy.data.actions.get(name)
        if act and act.users==0:bpy.data.actions.remove(act)
    assert_preserved(bpy,rig,meshes,prior)
    morphs=bake_new_muscle_clip(bpy,rig,meshes,a.clip)
    return len(settings.items),morphs


def export_game_glb(bpy,rig,meshes,output,expected_clips):
    use_object(bpy,rig)
    for ob in meshes:ob.hide_set(False);ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,
        export_animations=True,export_animation_mode='NLA_TRACKS',
        export_skins=True,export_morph=True,export_force_sampling=True,
        export_apply=False,export_cameras=False,export_lights=False)
    meta=glb_descriptor(output)
    animations=clip_names(meta)
    if not meta.get('skins') or not meta.get('meshes') or not expected_clips.issubset(animations):
        output.unlink(missing_ok=True)
        raise RuntimeError('GLB missing skinned character, original clips or new Rigger clip: '+str(sorted(expected_clips-animations)))


def main():
    import bpy
    a=args()
    if bpy.app.version < (4,2,0):raise RuntimeError('Rigger requires Blender 4.2 or newer')
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()))
    rig=bpy.data.objects.get('MONSTER_RIG')
    if not rig or rig.type!='ARMATURE':raise RuntimeError('Original MONSTER_RIG is missing')
    skinned=selected_game_meshes(bpy,rig)
    prior=capture(bpy,rig,skinned)
    # This import resolves ONLY if a verified external upstream Rigger exists.
    sys.path.insert(0,str(Path(a.rigger_dir).resolve()))
    import rigger
    if rigger.bl_info.get('name')!='Rigger' or tuple(rigger.bl_info.get('version',())) < (1,2,0):
        raise RuntimeError('Unexpected Rigger version or incompatible addon')
    rigger.register()
    output=Path(a.output).resolve()
    if a.mode=='controls':
        ctrl=create_controls(bpy,rig,skinned,prior)
        if output.suffix.lower()!='.blend':raise RuntimeError('Controls must save a .blend scene')
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        print('Non-destructive Rigger control rig:',ctrl.name)
    elif a.mode=='retarget':
        mappings,morphs=retarget_motion(bpy,rig,skinned,prior,a)
        if output.suffix.lower()=='.blend':
            bpy.ops.wm.save_as_mainfile(filepath=str(output))
        else:
            expected=prior['nla']|{a.clip}
            export_game_glb(bpy,rig,skinned,output,expected)
        print('Rigger transferred',mappings,'bone relationships and',morphs,'muscle morphs')
    else:
        from rigger import utils,export
        ctrl_rigs=[ob for ob in bpy.data.objects if ob.type=='ARMATURE' and utils.is_rig(ob)]
        if len(ctrl_rigs)!=1:raise RuntimeError('Need exactly one existing Rigger control rig in .blend')
        use_object(bpy,ctrl_rigs[0])
        settings=bpy.context.scene.rigger_export
        settings.file_format='GLB';settings.engine='GENERIC';settings.naming='RIGGER'
        settings.custom_script='';settings.bake_actions=True
        settings.anim_type='ACTIONS';settings.one_file_per='NONE';settings.include_meshes=True
        export.export_rig(bpy.context,ctrl_rigs[0],str(output),settings,run_script=False)
        data=glb_descriptor(output)
        if not data.get('skins') or not data.get('meshes'):
            output.unlink(missing_ok=True);raise RuntimeError('Rigger game output missing skin or meshes')
        assert_preserved(bpy,rig,skinned,prior)
        print('Upstream Rigger clean game skeleton exported:',output)

if __name__=='__main__':main()
