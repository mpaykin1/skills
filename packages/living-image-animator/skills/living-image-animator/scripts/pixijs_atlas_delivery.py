#!/usr/bin/env python3
"""Full original GIF->Godot->Blender->PixiJS+PathFinding, then atlas player.

Retains v0.20.1 original atlas workflow; optional A* is implemented in the
original standalone PixiJS HTML, not silently claimed by the atlas player.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from pixijs_atlas_bridge import build_atlas


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    p.add_argument('--pixelorama');p.add_argument('--opentoonz');p.add_argument('--mmpose-device')
    p.add_argument('--comfyui-url');p.add_argument('--godot');p.add_argument('--blender')
    p.add_argument('--pixi-js',type=Path)
    p.add_argument('--fetch-pixi',action='store_true')
    p.add_argument('--pathfinding-js',type=Path,help='Genuine browserified PathFinding.js 0.4.18')
    p.add_argument('--fetch-pathfinding',action='store_true',help='Download and build PathFinding.js via npm')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    out=a.out.resolve()
    original=Path(__file__).resolve().with_name('pixijs_delivery.py')
    cmd=[sys.executable,str(original),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js'):
        val=getattr(a,key.replace('-','_'))
        if val:cmd.extend(['--'+key,str(val)])
    if a.fetch_pixi:cmd.append('--fetch-pixi')
    if a.fetch_pathfinding:cmd.append('--fetch-pathfinding')
    if a.preflight_only:cmd.append('--preflight-only')
    status=subprocess.run(cmd,check=False)
    if status.returncode:raise SystemExit(status.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip'
    if not approved.is_file() or not (out/'living_scene_pixi.html').is_file():
        raise RuntimeError('Authentic upstream PixiJS and full-scene GIF/ZIP gate outputs required')
    engine=a.pixi_js
    if engine is None and (out/'vendor/pixi.min.js').is_file():engine=out/'vendor/pixi.min.js'
    atlas,meta=build_atlas(approved,out/'living_scene_pixi_atlas.html',engine,fps=a.fps,seconds=a.seconds)
    archive=out/'living_scene_pixi_atlas.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(atlas,'living_scene_pixi_atlas/index.html')
        z.writestr('living_scene_pixi_atlas/source.json',json.dumps({k:v for k,v in meta.items() if k!='engine_from'},ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        if 'project/browser/living_scene_pixi_atlas.zip' in z.namelist():
            raise RuntimeError('Duplicate PixiJS atlas packaging forbidden')
        z.write(archive,'project/browser/living_scene_pixi_atlas.zip')
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise RuntimeError('Atlas packaging damaged original assets ZIP')
    print(json.dumps({'atlas_html':str(atlas),'atlas_zip':str(archive),'assets_zip':str(approved),**meta},ensure_ascii=False))

if __name__=='__main__':main()
