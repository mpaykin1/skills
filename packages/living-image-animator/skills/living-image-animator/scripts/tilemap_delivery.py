#!/usr/bin/env python3
"""Full original GIF + Godot/Blender + PixiJS camera/FX/particles -> real GPU Tiled renderer."""
from __future__ import annotations
import argparse, json, subprocess, sys, zipfile
from pathlib import Path
from tilemap_vendor import vendor
from tilemap_bridge import patch_html, TilemapError

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--max-width',type=int,default=720)
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+k)
    for k in ('pixi-js','pathfinding-js','viewport-js','filters-js','particles-js'):
        p.add_argument('--'+k,type=Path)
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','preflight-only'):
        p.add_argument('--'+k,action='store_true')
    p.add_argument('--tilemap-js',type=Path,help='Genuine pinned @pixi/tilemap@5.0.2 browser UMD')
    p.add_argument('--fetch-tilemap',action='store_true')
    a=p.parse_args()
    out=a.out.resolve();out.mkdir(exist_ok=True,parents=True)
    tiles=a.tilemap_js
    if not a.preflight_only:
        if tiles is None and a.fetch_tilemap:tiles=vendor(out/'vendor/pixi-tilemap.js')
        if tiles is None or not tiles.is_file():p.error('Original tilemap JS not available. --fetch-tilemap or --tilemap-js required')
    previous=Path(__file__).resolve().with_name('pixi_particles_delivery.py')
    command=[sys.executable,str(previous),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
             '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js','viewport-js','filters-js','particles-js'):
        value=getattr(a,k.replace('-','_'))
        if value is not None:command.extend(['--'+k,str(value)])
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','preflight-only'):
        if getattr(a,k.replace('-','_')):command.append('--'+k)
    status=subprocess.run(command,check=False)
    if status.returncode:raise SystemExit(status.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip';prior=out/'living_scene_pixi_particles.html'
    if not approved.is_file() or not prior.is_file() or not (out/'living_scene.gif').is_file():
        raise TilemapError('Original GIF/ZIP/full PixiJS particle stage missing; cannot bypass original pose gates')
    html,source_assets,info=patch_html(prior,out/'living_scene_pixi_tilemap.html',approved,a.scene,tiles)
    license_file=Path(__file__).resolve().parent.parent/'references/LICENSE.pixi-tilemap.txt'
    if not license_file.is_file():raise TilemapError('Original MIT license file missing')
    package=out/'living_scene_pixi_tilemap.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_tilemap/index.html')
        z.write(license_file,'living_scene_pixi_tilemap/LICENSE.pixi-tilemap.txt')
        z.writestr('living_scene_pixi_tilemap/source_manifest.json',json.dumps(info,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        additions={'project/browser/living_scene_pixi_tilemap.zip':package.read_bytes(),
                   'project/licenses/LICENSE.pixi-tilemap.txt':license_file.read_bytes(),**dict(source_assets)}
        current=set(z.namelist())
        if any(k in current for k in additions):raise TilemapError('Already exported tilemap; use empty output directory')
        for name,blob in additions.items():z.writestr(name,blob)
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise TilemapError('Original source ZIP corrupted after tilemap export')
    print(json.dumps({'html':str(html),'tilemap_zip':str(package),'assets_zip':str(approved),**info},ensure_ascii=False))

if __name__=='__main__':main()
