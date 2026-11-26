#!/usr/bin/env python3
"""Strict original cel GIF -> viewport -> filters -> genuine PixiJS8 emitters.

All previous renderers and validators are mandatory. The emitted particle
stage is additive and never edits characters, collision metadata or source PNG.
"""
from __future__ import annotations
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
from pixi_particles_vendor import vendor
from pixi_particles_bridge import patch_html,runtime_bundle,ParticleBridgeError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48);p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+k)
    for k in ('pixi-js','pathfinding-js','viewport-js','filters-js','particles-js'):
        p.add_argument('--'+k,type=Path)
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','preflight-only'):
        p.add_argument('--'+k,action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    engine=a.particles_js
    if not a.preflight_only:
        if engine is None and a.fetch_particles:
            engine=vendor(out/'vendor/pixi-v8-particles.iife.js')
        runtime_bundle(engine)  # fail before expensive production rendering
    prev=Path(__file__).resolve().with_name('pixi_filters_delivery.py')
    cmd=[sys.executable,str(prev),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js','viewport-js','filters-js'):
        value=getattr(a,k.replace('-','_'))
        if value:cmd.extend(['--'+k,str(value)])
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','preflight-only'):
        if getattr(a,k.replace('-','_')):cmd.append('--'+k)
    r=subprocess.run(cmd,check=False)
    if r.returncode:raise SystemExit(r.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip';base=out/'living_scene_pixi_filters.html'
    if not approved.is_file() or not base.is_file() or not (out/'living_scene.gif').is_file():
        raise ParticleBridgeError('Original verified GIF, source ZIP, PixiJS filter HTML required')
    html,meta=patch_html(base,out/'living_scene_pixi_particles.html',approved,engine)
    license_path=Path(__file__).resolve().parent.parent/'references/LICENSE.pixi-v8-particles.txt'
    if not license_path.is_file():raise ParticleBridgeError('Official particles MIT license/attribution missing')
    package=out/'living_scene_pixi_particles.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_particles/index.html')
        z.write(license_path,'living_scene_pixi_particles/LICENSE.pixi-v8-particles.txt')
        z.writestr('living_scene_pixi_particles/config.json',json.dumps(meta,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        name='project/browser/living_scene_pixi_particles.zip'
        if name in z.namelist():raise ParticleBridgeError('Duplicate particle artifact; use a fresh output folder')
        z.write(package,name);z.write(license_path,'project/licenses/LICENSE.pixi-v8-particles.txt')
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise ParticleBridgeError('Original asset ZIP corrupted')
    print(json.dumps({'gif':str(out/'living_scene.gif'),'html':str(html),'particles_zip':str(package),
                      'assets_zip':str(approved),**meta},ensure_ascii=False))

if __name__=='__main__':main()
