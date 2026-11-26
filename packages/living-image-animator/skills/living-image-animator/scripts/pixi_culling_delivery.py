#!/usr/bin/env python3
"""Strict full-cel GIF/ZIP -> Tiled/PixiJS GPU tilemap -> native PixiJS 8 culling.

No external culling binary: the real PixiJS 8.23.0 code is already embedded by
upstream. Never reimplements culling by hiding original sprites manually.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from pixi_culling_bridge import patch_html, config_from_approved, CullingBridgeError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--scene',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--seconds',type=int,default=48)
    parser.add_argument('--max-width',type=int,default=720)
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        parser.add_argument('--'+key)
    for key in ('pixi-js','pathfinding-js','viewport-js','filters-js','particles-js','tilemap-js'):
        parser.add_argument('--'+key,type=Path)
    for key in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','fetch-tilemap','preflight-only'):
        parser.add_argument('--'+key,action='store_true')
    opts=parser.parse_args()
    out=opts.out.resolve();out.mkdir(parents=True,exist_ok=True)
    original=Path(__file__).resolve().with_name('tilemap_delivery.py')
    cmd=[sys.executable,str(original),str(opts.source.resolve()),'--scene',str(opts.scene.resolve()),
         '--out',str(out),'--fps',str(opts.fps),'--seconds',str(opts.seconds),
         '--max-width',str(opts.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender',
                'pixi-js','pathfinding-js','viewport-js','filters-js','particles-js','tilemap-js'):
        val=getattr(opts,key.replace('-','_'))
        if val is not None:cmd.extend(['--'+key,str(val)])
    for key in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters',
                'fetch-particles','fetch-tilemap','preflight-only'):
        if getattr(opts,key.replace('-','_')):cmd.append('--'+key)
    run=subprocess.run(cmd,check=False)
    if run.returncode:raise SystemExit(run.returncode)
    if opts.preflight_only:return
    approved=out/'living_scene_assets.zip'
    original_html=out/'living_scene_pixi_tilemap.html'
    if not approved.is_file() or not original_html.is_file() or not (out/'living_scene.gif').is_file():
        raise CullingBridgeError('Existing full approved GIF and real GPU tilemap HTML required')
    # Only a new additional browser output, never overwrite the original.
    html,info=patch_html(original_html,out/'living_scene_pixi_culled.html',approved)
    license_file=Path(__file__).resolve().parent.parent/'references'/'LICENSE.pixi-culler.txt'
    if not license_file.is_file():raise CullingBridgeError('Upstream PixiJS MIT license missing')
    bundle=out/'living_scene_pixi_culled.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_culled/index.html')
        z.write(license_file,'living_scene_pixi_culled/LICENSE.pixi-culler.txt')
        z.writestr('living_scene_pixi_culled/config.json',json.dumps(info,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        prior=set(z.namelist())
        members=['project/browser/living_scene_pixi_culled.zip','project/licenses/LICENSE.pixi-culler.txt']
        if any(m in prior for m in members):
            raise CullingBridgeError('Culled export already exists: use a clean out directory')
        z.write(bundle,members[0]);z.write(license_file,members[1])
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise CullingBridgeError('Original approved ZIP became corrupt')
    print(json.dumps({'html':str(html),'zip':str(bundle),'source_zip':str(approved),**info},ensure_ascii=False))

if __name__=='__main__':main()
