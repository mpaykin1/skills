"""Use the public operator of an already installed, reviewed Rokoko addon.
No add-on activation, account automation or authentication bypass. Separate output only.
"""
import argparse, json, sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from map_gate import validate,digest

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--motion',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);c=json.loads(a.config.read_text());validate(c)
    srcpath=Path(bpy.data.filepath).resolve();out=a.out.resolve()
    if not srcpath.is_file() or digest(srcpath)!=c['source_sha256'] or digest(a.motion)!=c['motion_sha256']:raise ValueError('input hash mismatch')
    if out==srcpath or out.exists() or out.suffix!='.blend':raise ValueError('new .blend output required')
    if bpy.app.version[:2]!=(4,5):raise RuntimeError('reviewed backend is Blender 4.5; other versions blocked')
    if not hasattr(bpy.context.scene,'rsl_retargeting_bone_list'):raise RuntimeError('Rokoko not registered; install approved addon and authorize normally')
    src=bpy.data.objects[c['source_rig']];tgt=bpy.data.objects[c['target_rig']]
    if any(o.type!='ARMATURE' for o in (src,tgt)):raise ValueError('armatures required')
    if not src.animation_data or not src.animation_data.action or src.animation_data.action.name!=c['source_action']:raise ValueError('source action mismatch')
    old_actions=set(bpy.data.actions.keys());old_action=src.animation_data.action
    if c['new_action'] in old_actions:raise ValueError('new action name already exists')
    if tgt.animation_data and (tgt.animation_data.action or len(tgt.animation_data.nla_tracks)):raise ValueError('use a dedicated empty target animation slot/working copy')
    if any(b.constraints for b in tgt.pose.bones):raise ValueError('target must be reviewed unconstrained transfer skeleton; use existing Rigify IK/FK transfer and layers afterwards')
    rows=validate(c,set(src.pose.bones.keys()),set(tgt.pose.bones.keys()))
    scene=bpy.context.scene
    if abs(scene.render.fps/scene.render.fps_base-c['fps'])>1e-5:raise ValueError('FPS mismatch')
    lo,hi=old_action.frame_range
    if abs(lo-c['start'])>1e-4 or abs(hi-c['end'])>1e-4:raise ValueError('action range mismatch')
    if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    scene.frame_set(c['start']);scene.rsl_retargeting_armature_source=src;scene.rsl_retargeting_armature_target=tgt
    scene.rsl_retargeting_auto_scaling=c['auto_scale'];scene.rsl_retargeting_use_pose=c['pose']
    bone_list=scene.rsl_retargeting_bone_list;bone_list.clear()
    for row in rows:
        item=bone_list.add();item.bone_name_source=row['source'];item.bone_name_target=row['target'];item.is_custom=True
    # Use the registered upstream operator, not any private login or UI state override.
    if not bpy.ops.rsl.retarget_animation.poll():raise RuntimeError('Rokoko operator unavailable in current authorized context')
    result=bpy.ops.rsl.retarget_animation()
    if 'FINISHED' not in result or not tgt.animation_data or not tgt.animation_data.action:raise RuntimeError('Rokoko retarget not completed')
    act=tgt.animation_data.action
    if act.name in old_actions or act==old_action:raise RuntimeError('no new action produced')
    if abs(act.frame_range[0]-lo)>1e-4 or abs(act.frame_range[1]-hi)>1e-4:raise RuntimeError('retarget changed clip timing')
    act.name=c['new_action'];act.use_fake_user=True
    act['hero_id']=c['hero_id'];act['motion_sha256']=c['motion_sha256'];act['retarget_backend']='rokoko-1.4.4';act['root_mode_requested']=c['root_mode'];act['motion_review']='pending'
    if digest(srcpath)!=c['source_sha256']:raise RuntimeError('original input changed')
    out.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print('New retargeted transfer action saved; Rigify transfer, root policy, contacts and visual approval pending')
if __name__=='__main__':main()
