#!/usr/bin/env python3
"""Full original sprite artwork release gate -> additional Godot4 Shader Stacker ZIP.

No bypass of SAM2/Krita/OpenToonz/Pixelorama/ControlNet source gate. Old
validated GIF/PNG/Godot/Blender/Three.js/PixiJS exports remain independent.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
from shader_stacker_bridge import project

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--max-width',type=int,default=720)
    for field in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot'):
        p.add_argument('--'+field)
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    if a.fps<24 or not 40<=a.seconds<=60:p.error('Preserve original 24+ fps, 40-60s full-pose release gate')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    pre=Path(__file__).resolve().with_name('godot_delivery.py')
    cmd=[sys.executable,str(pre),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),
         '--max-width',str(a.max_width)]
    for field in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot'):
        val=getattr(a,field.replace('-','_'))
        if val:cmd.extend(['--'+field,str(val)])
    if a.preflight_only:cmd.append('--preflight-only')
    check=subprocess.run(cmd,check=False)
    if check.returncode:raise SystemExit(check.returncode)
    if a.preflight_only:return
    source_zip=out/'living_scene_assets.zip'
    native_zip=out/'living_scene_godot.zip'
    if not source_zip.is_file() or not native_zip.is_file() or not (out/'living_scene.gif').is_file():
        p.error('Previous original full-body GIF + source ZIP + native Godot project required')
    addon_zip,meta=project(source_zip,a.scene.resolve(),native_zip,out,godot_binary=a.godot)
    print(json.dumps({'godot_shader_stacker_zip':str(addon_zip),
                      'original_gif':str(out/'living_scene.gif'),
                      'original_godot_zip':str(native_zip),
                      'original_source_zip':str(source_zip),**meta},ensure_ascii=False))

if __name__=='__main__':main()
