#!/usr/bin/env python3
"""Full original animation/physics/mobile-controls chain -> genuine YUKA NPC AI.

Never relax any original character, motion, identity, map, or collision gate.
Produces a distinct fully offline HTML and ZIP, not a replacement for prior art.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from yuka_vendor import vendor,locate
from yuka_bridge import patch_html,YukaBridgeError

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for name in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+name)
    for name in ('pixi-js','pathfinding-js','matter-js','nipple-js','yuka-js'):
        p.add_argument('--'+name,type=Path)
    for name in ('fetch-pixi','fetch-pathfinding','fetch-matter','fetch-nipple','fetch-yuka','preflight-only'):
        p.add_argument('--'+name,action='store_true')
    a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if not a.source.is_file():p.error('Original source art is missing')
    if a.fps<24:p.error('Original source sprites must run >=24fps')
    engine=a.yuka_js
    if not a.preflight_only:
        if a.fetch_yuka and engine is None:engine=vendor(out/'vendor'/'yuka.js')
        locate(engine) # block before expensive upstream pose rendering
    upstream=Path(__file__).with_name('nipplejs_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),
         '--scene',str(a.scene.resolve()),'--out',str(out),
         '--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for name in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender',
                 'pixi-js','pathfinding-js','matter-js','nipple-js'):
        value=getattr(a,name.replace('-','_'))
        if value:cmd.extend(['--'+name,str(value)])
    for name in ('fetch-pixi','fetch-pathfinding','fetch-matter','fetch-nipple','preflight-only'):
        if getattr(a,name.replace('-','_')):cmd.append('--'+name)
    result=subprocess.run(cmd,check=False)
    if result.returncode:raise SystemExit(result.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip'
    old=out/'living_scene_pixi_controls.html'
    gif=out/'living_scene.gif'
    if not approved.is_file() or not old.is_file() or not gif.is_file():
        raise YukaBridgeError('Original GIF/source ZIP and authentic PixiJS physical joystick player are required')
    html,metadata=patch_html(old,out/'living_scene_pixi_ai.html',approved,engine)
    license_path=Path(__file__).parent.parent/'references'/'LICENSE.yuka.txt'
    if not license_path.is_file():raise YukaBridgeError('Upstream YUKA MIT attribution missing')
    package=out/'living_scene_pixi_ai.zip'
    if package.exists():raise YukaBridgeError('NPC AI package already exists; choose fresh output directory')
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_ai/index.html')
        z.write(license_path,'living_scene_pixi_ai/LICENSE.yuka.txt')
        z.writestr('living_scene_pixi_ai/config.json',json.dumps(metadata,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        names=('project/browser/living_scene_pixi_ai.zip','project/licenses/LICENSE.yuka.txt')
        if any(x in z.namelist() for x in names):
            raise YukaBridgeError('YUKA package already included; use a fresh output directory')
        z.write(package,names[0]);z.write(license_path,names[1])
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise YukaBridgeError('Original approved actor ZIP damaged')
    print(json.dumps({'ai_html':str(html),'ai_zip':str(package),
                      'original_gif':str(gif),'original_asset_zip':str(approved),
                      **metadata},ensure_ascii=False))

if __name__=='__main__':main()
