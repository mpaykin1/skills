#!/usr/bin/env python3
"""Full strict sprite-animation->Godot->Blender->PixiJS+PathFinding/atlas->pixi-viewport.

Real pixi-viewport runs ONLY AFTER approved actor sprite validation. Works on
actual local PixiJS v8 + pixi-viewport v7 UMD files; never uses a CDN/fallback.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path
import zipfile
from pixi_viewport_vendor import vendor
from pixi_viewport_bridge import patch_atlas_html, viewport_bundle, ViewportBridgeError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--scene',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--seconds',type=int,default=48)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--max-width',type=int,default=720)
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        parser.add_argument('--'+key)
    parser.add_argument('--pixi-js',type=Path)
    parser.add_argument('--fetch-pixi',action='store_true')
    parser.add_argument('--pathfinding-js',type=Path)
    parser.add_argument('--fetch-pathfinding',action='store_true')
    parser.add_argument('--viewport-js',type=Path)
    parser.add_argument('--fetch-viewport',action='store_true')
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    engine=args.viewport_js
    if args.fetch_viewport and engine is None and not args.preflight_only:
        engine=vendor(out/'vendor'/'pixi_viewport.umd.cjs')
    if not args.preflight_only:
        viewport_bundle(engine)  # fail before rendering thousands of GIF frames
    cmd=[sys.executable,str(Path(__file__).with_name('pixijs_atlas_delivery.py')),
         str(args.source.resolve()),'--scene',str(args.scene.resolve()),'--out',str(out),
         '--seconds',str(args.seconds),'--fps',str(args.fps),'--max-width',str(args.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js'):
        value=getattr(args,key.replace('-','_'))
        if value:cmd.extend(['--'+key,str(value)])
    for key in ('fetch-pixi','fetch-pathfinding','preflight-only'):
        if getattr(args,key.replace('-','_')):cmd.append('--'+key)
    done=subprocess.run(cmd,check=False)
    if done.returncode:raise SystemExit(done.returncode)
    if args.preflight_only:return
    approved=out/'living_scene_assets.zip'
    atlas=out/'living_scene_pixi_atlas.html'
    if not approved.is_file() or not atlas.is_file():
        raise ViewportBridgeError('Prior animation stages did not produce approved assets and actual PixiJS atlas')
    html,stats=patch_atlas_html(atlas,out/'living_scene_pixi_viewport.html',approved,engine)
    ref=Path(__file__).parent.parent/'references'/'pixi-viewport-LICENSE.txt'
    if not ref.is_file():raise ViewportBridgeError('Official pixi-viewport MIT license missing')
    package=out/'living_scene_pixi_viewport.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_viewport/index.html')
        z.write(ref,'living_scene_pixi_viewport/LICENSE.pixi-viewport.txt')
        z.writestr('living_scene_pixi_viewport/config.json',json.dumps(stats,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        member='project/browser/living_scene_pixi_viewport.zip'
        if member in z.namelist():raise ViewportBridgeError('A viewport package already exists; choose a fresh output directory')
        z.write(package,member)
        z.write(ref,'project/licenses/LICENSE.pixi-viewport.txt')
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise ViewportBridgeError('Final approved assets ZIP became corrupt')
    print(json.dumps({'gif':str(out/'living_scene.gif'),
                      'viewport_html':str(html),'viewport_zip':str(package),
                      'assets_zip':str(approved),**stats},ensure_ascii=False))

if __name__=='__main__':main()
