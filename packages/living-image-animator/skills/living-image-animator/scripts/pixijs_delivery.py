#!/usr/bin/env python3
"""Final PixiJS offline HTML export after ALL original GIF, Godot and Blender gates."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from pixijs_bridge import build_html, PixiBridgeError
from pixijs_vendor import vendor
from pathfinding_vendor import vendor as vendor_pathfinding

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
    p.add_argument('--godot')
    p.add_argument('--blender')
    p.add_argument('--pixi-js',type=Path,help='Genuine pinned pixi.js@8.23.0 dist/pixi.min.js')
    p.add_argument('--fetch-pixi',action='store_true',help='Download exact npm package using npm pack when a real local bundle is absent')
    p.add_argument('--pathfinding-js',type=Path,help='Genuine browserified pathfinding@0.4.18')
    p.add_argument('--fetch-pathfinding',action='store_true',help='Install and bundle open-source PathFinding.js using npm')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    out=a.out.resolve();scene=a.scene.resolve()
    if not a.source.is_file():p.error('Source image missing')
    if a.fps<24:p.error('Full-cel animation must run at >=24fps')
    engine=a.pixi_js
    if a.fetch_pixi and engine is None:
        engine=vendor(out/'vendor'/'pixi.min.js')
    if not a.preflight_only:
        # Fail BEFORE long upstream rendering if a real standalone runtime is missing.
        from pixijs_bridge import bundle_path
        bundle_path(engine)
    pathfinding_engine=a.pathfinding_js
    if a.fetch_pathfinding and pathfinding_engine is None:
        pathfinding_engine=vendor_pathfinding(out/'vendor'/'pathfinding-browser.js')
    upstream=Path(__file__).with_name('blender_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(scene),
         '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),
         '--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        value=getattr(a,key.replace('-','_'))
        if value:cmd.extend(['--'+key,str(value)])
    if a.preflight_only:cmd.append('--preflight-only')
    proc=subprocess.run(cmd,check=False)
    if proc.returncode:raise SystemExit(proc.returncode)
    if a.preflight_only:return
    zip_path=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    if not zip_path.is_file() or not gif.is_file():raise PixiBridgeError('Upstream full-cel animation was not certified')
    html,metadata=build_html(zip_path,out/'living_scene_pixi.html',engine,pathfinding_js=pathfinding_engine)
    with zipfile.ZipFile(zip_path,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        member='project/browser/living_scene_pixi.html'
        if member in z.namelist():raise PixiBridgeError('Duplicate browser project; use an empty output directory')
        z.write(html,member)
        z.writestr('pixijs_integration.json',json.dumps(metadata,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip() is not None:raise PixiBridgeError('Final asset ZIP is corrupt')
    print(json.dumps({'gif':str(gif),'assets_zip':str(zip_path),'standalone_html':str(html),**metadata},ensure_ascii=False))

if __name__=='__main__':main()
