#!/usr/bin/env python3
"""Godot + Blender Grease Pencil 2.5D output after unchanged original pose gates.

Every upstream gate remains mandatory. Produces original GIF, assets ZIP,
Godot project ZIP, plus Blender 2.5D project ZIP (editable source script;
native .blend only if actual Blender binary is run successfully).
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image
from blender_bridge import compile_project, BlenderBridgeError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    p.add_argument('--pixelorama')
    p.add_argument('--opentoonz')
    p.add_argument('--mmpose-device')
    p.add_argument('--comfyui-url')
    p.add_argument('--godot',help='Optional real Godot binary to validate Godot project')
    p.add_argument('--blender',help='Optional real Blender 4.5+ binary to build .blend')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    out=a.out.resolve()
    upstream=Path(__file__).resolve().with_name('godot_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),
         '--max-width',str(a.max_width)]
    for key,value in [('pixelorama',a.pixelorama),('opentoonz',a.opentoonz),
                      ('mmpose-device',a.mmpose_device),('comfyui-url',a.comfyui_url),
                      ('godot',a.godot)]:
        if value:cmd.extend(['--'+key,value])
    if a.preflight_only:cmd.append('--preflight-only')
    proc=subprocess.run(cmd,check=False)
    if proc.returncode:raise SystemExit(proc.returncode)
    if a.preflight_only:return
    assets=out/'living_scene_assets.zip'
    source_gif=out/'living_scene.gif'
    godot=out/'living_scene_godot.zip'
    if any(not p.is_file() for p in (assets,source_gif,godot)):
        raise BlenderBridgeError('one of validated upstream outputs is absent')
    # Original Blender-only depth plates may not have been copied by the Godot
    # stage; add authentic source-registered PNGs without touching any cel.
    original_scene=json.loads(a.scene.resolve().read_text('utf8'))
    layer_entries=original_scene.get('blender',{}).get('layers',[])
    if layer_entries:
        with Image.open(a.source.resolve()) as src:
            size=src.size
        with zipfile.ZipFile(assets,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            current=set(z.namelist())
            for entry in layer_entries:
                if not isinstance(entry,dict):raise BlenderBridgeError('Invalid authored depth plane')
                raw=entry.get('png')
                if (not isinstance(raw,str) or not raw or raw.startswith('/')
                    or '\\' in raw or any(x in ('','.','..') for x in raw.split('/'))):
                    raise BlenderBridgeError('Unsafe Blender depth plate path')
                file=(a.scene.resolve().parent/raw).resolve()
                root=a.scene.resolve().parent
                if root not in file.parents or not file.is_file():
                    raise BlenderBridgeError('Missing authored Blender depth plate '+raw)
                with Image.open(file) as png:
                    if png.format!='PNG' or png.size!=size:
                        raise BlenderBridgeError('Blender depth plates must align with source canvas: '+raw)
                    lo,hi=png.convert('RGBA').getchannel('A').getextrema()
                    if lo==255 or hi==0:
                        raise BlenderBridgeError('Blender depth plates require transparent silhouettes: '+raw)
                member='project/inputs/'+raw
                if member not in current:
                    z.write(file,member)
                    current.add(member)
    bundle,meta=compile_project(assets,out,a.fps,a.seconds,a.blender)
    with zipfile.ZipFile(assets,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        existing=set(z.namelist())
        target='project/blender/living_scene_blender.zip'
        if target in existing:raise BlenderBridgeError('Blender export already embedded; refusing duplicate')
        z.write(bundle,target)
        z.writestr('blender_grease_pencil_integration.json',json.dumps({
            'technology':'Blender Grease Pencil v3 + original painted 2.5D planes',
            'native_blend_created':meta['blender_scene_file'],
            'verified_pose_gate_preserved':True,
            'source_sprite_deformation':False,
            **meta},ensure_ascii=False,indent=2))
    with zipfile.ZipFile(assets) as z:
        if z.testzip() is not None:raise BlenderBridgeError('final source ZIP became corrupt')
    print(json.dumps({'gif':str(source_gif),'assets_zip':str(assets),
                      'godot_zip':str(godot),'blender_zip':str(bundle),**meta},ensure_ascii=False))

if __name__=='__main__':main()
