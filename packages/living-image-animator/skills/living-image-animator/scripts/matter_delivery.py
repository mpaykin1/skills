#!/usr/bin/env python3
"""Full independent motion gate -> PixiJS+PathFinding -> additive Matter.js 2D physics.

Never substitutes collision-only motion for genuine authored full-character art.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from matter_vendor import vendor,locate
from matter_bridge import build_html


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for option in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+option)
    p.add_argument('--pixi-js',type=Path)
    p.add_argument('--pathfinding-js',type=Path)
    p.add_argument('--matter-js',type=Path,help='Genuine matter-js@0.20.0 browser UMD')
    p.add_argument('--fetch-pixi',action='store_true')
    p.add_argument('--fetch-pathfinding',action='store_true')
    p.add_argument('--fetch-matter',action='store_true')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    if not a.source.is_file():p.error('Original illustration not found')
    if a.fps<24:p.error('Original cel animation requires >=24fps')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    matter=a.matter_js
    if not a.preflight_only:
        if matter is None and a.fetch_matter:matter=vendor(out/'vendor'/'matter.min.js')
        locate(matter) # no fake offline HTML; fail before expensive original render
    upstream=Path(__file__).resolve().with_name('pixijs_delivery.py')
    command=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
             '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),
             '--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js'):
        value=getattr(a,key.replace('-','_'))
        if value:command.extend(['--'+key,str(value)])
    for key in ('fetch-pixi','fetch-pathfinding','preflight-only'):
        if getattr(a,key.replace('-','_')):command.append('--'+key)
    proc=subprocess.run(command,check=False)
    if proc.returncode:raise SystemExit(proc.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip'
    if not approved.is_file() or not (out/'living_scene.gif').is_file() or not (out/'living_scene_pixi.html').is_file():
        raise RuntimeError('Authentic full-cel GIF + source and PixiJS browser build required')
    pixi=a.pixi_js or ((out/'vendor/pixi.min.js') if (out/'vendor/pixi.min.js').is_file() else None)
    path=a.pathfinding_js or ((out/'vendor/pathfinding-browser.js') if (out/'vendor/pathfinding-browser.js').is_file() else None)
    html,info=build_html(approved,out/'living_scene_pixi_physics.html',pixi,path,matter)
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for member in ('project/browser/living_scene_pixi_physics.html','matterjs_integration.json'):
            if member in z.namelist():raise RuntimeError('Physics output already in ZIP; use a new out directory')
        z.write(html,'project/browser/living_scene_pixi_physics.html')
        z.writestr('matterjs_integration.json',json.dumps(info,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise RuntimeError('Source ZIP damaged after physics stage')
    print(json.dumps({'physics_html':str(html),'source_zip':str(approved),**info},ensure_ascii=False))

if __name__=='__main__':main()
