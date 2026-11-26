#!/usr/bin/env python3
"""Original PNG/GIF + Godot/Blender -> real SpriteStack2D native Godot scene.

Addon is source-locked MIT code, installed only from genuine official GitHub
checkout. No character cel pixel or original Z-stack slice is ever modified.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from spritestack2d_vendor import install,validate,SpriteStack2DVendorError
from spritestack2d_bridge import project,Stack2DBridgeError


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path)
    ap.add_argument('--scene',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seconds',type=int,default=48)
    ap.add_argument('--fps',type=int,default=24)
    ap.add_argument('--max-width',type=int,default=720)
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        ap.add_argument('--'+k)
    ap.add_argument('--addon-root',type=Path,help='Genuine official SpriteStack2D checkout with original LICENSE')
    ap.add_argument('--fetch-addon',action='store_true',help='Install real pinned MIT SpriteStack2D from GitHub once before exporting')
    ap.add_argument('--preflight-only',action='store_true')
    args=ap.parse_args()
    if not args.source.is_file() or not args.scene.is_file():ap.error('Original image and original scene.json required')
    if args.fps<24 or not 40<=args.seconds<=60:ap.error('Original full-pose 24+fps, 40–60s quality requirements cannot be weakened')
    if args.fetch_addon and args.addon_root:ap.error('Use either --fetch-addon or --addon-root')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    addon=args.addon_root
    if not args.preflight_only:
        if args.fetch_addon:
            addon=install(out/'vendor/spritestack2d/addons/sprite_stack_2d')
        if addon is None:ap.error('Genuine SpriteStack2D addon missing; provide --fetch-addon or --addon-root')
        validate(addon)
    upstream=Path(__file__).with_name('blender_delivery.py')
    cmd=[sys.executable,str(upstream),str(args.source.resolve()),'--scene',str(args.scene.resolve()),
         '--out',str(out),'--seconds',str(args.seconds),'--fps',str(args.fps),'--max-width',str(args.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        value=getattr(args,k.replace('-','_'))
        if value:cmd.extend(['--'+k,str(value)])
    if args.preflight_only:cmd.append('--preflight-only')
    result=subprocess.run(cmd,check=False)
    if result.returncode:raise SystemExit(result.returncode)
    if args.preflight_only:return
    original=out/'living_scene_assets.zip'
    gif=out/'living_scene.gif'
    old_godot=out/'living_scene_godot.zip'
    if any(not v.is_file() for v in (original,gif,old_godot)):
        raise Stack2DBridgeError('Original approved pose GIF/source ZIP and native Godot project required')
    pack,meta=project(original,args.scene,out/'godot_project',addon,
                      out/'living_scene_godot_spritestack2d_project',args.godot)
    lic=out/'living_scene_godot_spritestack2d_project/LICENSE.SpriteStack2D.txt'
    with zipfile.ZipFile(original,'a',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        members=('project/godot/living_scene_godot_spritestack2d.zip',
                 'project/licenses/LICENSE.SpriteStack2D.txt')
        if any(m in z.namelist() for m in members):raise Stack2DBridgeError('Stack2D already exported; use clean output')
        z.write(pack,members[0]);z.write(lic,members[1])
    with zipfile.ZipFile(original) as z:
        if z.testzip() is not None:raise Stack2DBridgeError('Original source ZIP damaged after native SpriteStack2D addition')
    print(json.dumps({'original_gif':str(gif),'original_asset_zip':str(original),
                      'original_godot_zip':str(old_godot),'native_sprite_stack2d_zip':str(pack),**meta},ensure_ascii=False))

if __name__=='__main__':main()
