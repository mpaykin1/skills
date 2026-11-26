#!/usr/bin/env python3
"""Approved source artwork -> GIF/source ZIP -> actual PixiJS/A*/Matter physics -> nipplejs controls.

Never skips or replaces prior original-character art validation. The new
interactive browser HTML is additive to previous standalone render outputs.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from nipplejs_vendor import vendor,locate
from nipplejs_bridge import patch_html,NippleBridgeError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+k)
    for k in ('pixi-js','pathfinding-js','matter-js','nipple-js'):
        p.add_argument('--'+k,type=Path)
    for k in ('fetch-pixi','fetch-pathfinding','fetch-matter','fetch-nipple','preflight-only'):
        p.add_argument('--'+k,action='store_true')
    a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if not a.source.is_file():p.error('Original source illustration is missing')
    if a.fps<24:p.error('Original full-body PNG animation requires >=24 fps')
    controller=a.nipple_js
    if not a.preflight_only:
        if a.fetch_nipple and controller is None:
            controller=vendor(out/'vendor/nipplejs.min.js')
        locate(controller)  # fail before expensive native source rendering
    cmd=[sys.executable,str(Path(__file__).with_name('matter_delivery.py')),
         str(a.source.resolve()),'--scene',str(a.scene.resolve()),'--out',str(out),
         '--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js','matter-js'):
        value=getattr(a,k.replace('-','_'))
        if value:cmd.extend(['--'+k,str(value)])
    for k in ('fetch-pixi','fetch-pathfinding','fetch-matter','preflight-only'):
        if getattr(a,k.replace('-','_')):cmd.append('--'+k)
    done=subprocess.run(cmd,check=False)
    if done.returncode:raise SystemExit(done.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip';physics=out/'living_scene_pixi_physics.html';gif=out/'living_scene.gif'
    if not approved.is_file() or not physics.is_file() or not gif.is_file():
        raise NippleBridgeError('Original full-cel GIF/ZIP, real Matter.js physical HTML and A* required')
    result,meta=patch_html(physics,out/'living_scene_pixi_controls.html',approved,controller)
    lic=Path(__file__).resolve().parent.parent/'references'/'LICENSE.nipplejs.txt'
    if not lic.is_file():raise NippleBridgeError('Official nipplejs MIT attribution file missing')
    pack=out/'living_scene_pixi_controls.zip'
    if pack.exists():raise NippleBridgeError('Controls ZIP exists; use fresh output directory')
    with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(result,'living_scene_pixi_controls/index.html')
        z.write(lic,'living_scene_pixi_controls/LICENSE.nipplejs.txt')
        z.writestr('living_scene_pixi_controls/controls.json',json.dumps(meta,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        entries=('project/browser/living_scene_pixi_controls.zip','project/licenses/LICENSE.nipplejs.txt')
        if any(n in z.namelist() for n in entries):raise NippleBridgeError('Duplicate physics controls packaging')
        z.write(pack,entries[0]);z.write(lic,entries[1])
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise NippleBridgeError('Source actor ZIP damaged after controls export')
    print(json.dumps({'game_html':str(result),'game_zip':str(pack),'gif':str(gif),
                      'source_zip':str(approved),**meta},ensure_ascii=False))

if __name__=='__main__':main()
