#!/usr/bin/env python3
"""Start verified Rigger addon + Monster Anatomy integration in Blender.

The original creature is always read-only and preserved as-is.
Optional explicit modes: controls (non-destructive Rigger IK/FK rig), retarget
(transfer a real animated source), export (clean game armature from controls).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from download_rigger import verify


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',required=True,choices=['controls','retarget','export'])
    p.add_argument('--blender',default=os.getenv('BLENDER_BIN','blender'))
    p.add_argument('--rigger-dir',required=True)
    p.add_argument('--blend',required=True)
    p.add_argument('--output-blend',default='')
    p.add_argument('--output-glb',default='')
    p.add_argument('--motion',default='',help='Original animated FBX/GLB with armature (retarget only)')
    p.add_argument('--motion-rig',default='')
    p.add_argument('--motion-action',default='')
    p.add_argument('--bone-map',default='',help='Optional source bone -> MONSTER_RIG bone JSON')
    p.add_argument('--clip',default='RIGGER_NEW_ACTION')
    p.add_argument('--in-place',action='store_true')
    args=p.parse_args()
    verify(Path(args.rigger_dir).expanduser().resolve())
    original=Path(args.blend).resolve()
    if not original.is_file() or original.suffix.lower()!='.blend':p.error('Real input .blend scene required')
    if args.mode=='controls':
        if args.motion or args.bone_map or not args.output_blend or args.output_glb:p.error('Controls writes only a NEW .blend; no motion/bone map')
    if args.mode=='retarget':
        motion=Path(args.motion).expanduser().resolve() if args.motion else None
        if not motion or not motion.is_file() or motion.suffix.lower() not in ('.glb','.fbx'):p.error('Retarget requires an existing animated .glb/.fbx motion source')
        if bool(args.output_blend)==bool(args.output_glb):p.error('Retarget requires exactly one .blend or .glb destination')
    if args.mode=='export':
        if not args.output_glb or args.motion or args.bone_map or args.output_blend:p.error('Export writes only a NEW .glb from Rigger controls')
    output=Path(args.output_blend or args.output_glb).resolve()
    if output==original or output.exists():p.error('Output must be a NEW file, not an existing file or the input')
    if args.motion and Path(args.motion).resolve() in (original,output):p.error('Motion source must be separate')
    if args.bone_map and not Path(args.bone_map).is_file():p.error('Bone map must exist')
    output.parent.mkdir(parents=True,exist_ok=True)
    blender=Path(args.blender).expanduser().resolve() if os.path.sep in args.blender else args.blender
    import shutil
    if not (Path(blender).is_file() if isinstance(blender,Path) else shutil.which(blender)):
        p.error('Blender 4.2+ binary not installed, provide --blender')
    script=ROOT/'rigger_monster_blender.py'
    command=[str(blender),'--background','--factory-startup','--python-exit-code','5',
             '--python',str(script),'--','--mode',args.mode,'--rigger-dir',str(Path(args.rigger_dir).resolve()),
             '--blend',str(original),'--output',str(output),'--clip',args.clip]
    if args.motion:command+=['--motion',str(Path(args.motion).resolve())]
    if args.motion_rig:command+=['--motion-rig',args.motion_rig]
    if args.motion_action:command+=['--motion-action',args.motion_action]
    if args.bone_map:command+=['--bone-map',str(Path(args.bone_map).resolve())]
    if args.in_place:command+=['--in-place']
    try:subprocess.run(command,check=True,timeout=1800)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        if output.is_file():output.unlink()  # never leave a half-baked 'success' export
        raise RuntimeError('Rigger Blender integration failed; original creature was not modified') from exc
    if not output.is_file() or output.stat().st_size<1024:
        raise RuntimeError('Rigger failed to produce a plausible output artifact')
    print('Rigger output:',output)

if __name__=='__main__':main()
