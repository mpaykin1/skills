#!/usr/bin/env python3
"""Full original cel gates -> Pixi viewport -> official filters -> v8 particle engine.

The previous scripts, original actor pixels, GIF, authored world, physics HTML
and all genuine engine licenses remain unmodified. Produces a further HTML.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from particle_emitter_vendor import vendor
from particle_emitter_bridge import create_html,runtime_binary,ParticleBridgeError

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for name in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+name)
    for name in ('pixi-js','pathfinding-js','viewport-js','filters-js','particles-js'):
        p.add_argument('--'+name,type=Path)
    for name in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','preflight-only'):
        p.add_argument('--'+name,action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    engine=a.particles_js
    if not a.preflight_only:
        if a.fetch_particles and engine is None:engine=vendor(out/'vendor'/'pixi-particle-emitter.min.js')
        runtime_binary(engine) # do not waste time on full 40-60s GIF if missing real library
    upstream=Path(__file__).with_name('pixi_filters_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for name in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender',
                 'pixi-js','pathfinding-js','viewport-js','filters-js'):
        value=getattr(a,name.replace('-','_'))
        if value:cmd.extend(['--'+name,str(value)])
    for name in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','preflight-only'):
        if getattr(a,name.replace('-','_')):cmd.append('--'+name)
    result=subprocess.run(cmd,check=False)
    if result.returncode:raise SystemExit(result.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip';filters=out/'living_scene_pixi_filters.html'
    if not approved.is_file() or not filters.is_file() or not (out/'living_scene.gif').is_file():
        raise ParticleBridgeError('Previous authentic full pose GIF+ZIP and PixiJS Filters HTML are mandatory')
    html,info=create_html(filters,out/'living_scene_pixi_particles.html',approved,engine)
    license_file=out/'vendor'/'LICENSE.v8-particle-emitter.txt'
    if not license_file.is_file():license_file=Path(__file__).resolve().parent.parent/'references'/'LICENSE.v8-particle-emitter.txt'
    if not license_file.is_file():raise ParticleBridgeError('Original MIT license unavailable for packaged particle engine')
    bundle=out/'living_scene_pixi_particles.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_particles/index.html')
        z.write(license_file,'living_scene_pixi_particles/LICENSE.v8-particle-emitter.txt')
        z.writestr('living_scene_pixi_particles/config.json',json.dumps(info,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        member='project/browser/living_scene_pixi_particles.zip'
        if member in z.namelist():raise ParticleBridgeError('Particle HTML already included in approved assets; use fresh out directory')
        z.write(bundle,member)
        z.write(license_file,'project/licenses/LICENSE.v8-particle-emitter.txt')
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise ParticleBridgeError('Original artist assets became damaged after packaging')
    print(json.dumps({'particle_html':str(html),'particle_zip':str(bundle),'assets_zip':str(approved),**info},ensure_ascii=False))

if __name__=='__main__':main()
