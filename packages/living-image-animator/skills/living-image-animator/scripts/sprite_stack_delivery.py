#!/usr/bin/env python3
"""Full original 2D-quality gate -> independent, real Three.js volumetric sprite stacking.
Existing GIF/source ZIP/Godot/Blender/PixiJS/FFmpeg and NPC flows remain separate.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, zipfile
from pathlib import Path
from sprite_stack_bridge import package, StackError
from sprite_stack_vendor import vendor

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48);p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for arg in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+arg)
    p.add_argument('--three-js',type=Path,help='Genuine official three@0.187.0/build/three.module.js')
    p.add_argument('--fetch-three',action='store_true',help='Download genuine npm three@0.187.0, requires network')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(exist_ok=True,parents=True)
    if a.fps<24 or not 40<=a.seconds<=60:p.error('Existing original full-cel animation requires >=24 FPS and 40–60 seconds')
    engine=a.three_js
    if not a.preflight_only:
        if engine is None and a.fetch_three:engine=vendor(out/'vendor/three.module.js')
        if engine is None or not engine.is_file():p.error('Genuine Three.js bundle absent. Supply --three-js or --fetch-three')
    previous=Path(__file__).resolve().with_name('blender_delivery.py')
    cmd=[sys.executable,str(previous),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),'--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        val=getattr(a,key.replace('-','_'))
        if val:cmd.extend(['--'+key,str(val)])
    if a.preflight_only:cmd.append('--preflight-only')
    done=subprocess.run(cmd,check=False)
    if done.returncode:raise SystemExit(done.returncode)
    if a.preflight_only:return
    srczip=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    if not srczip.is_file() or not gif.is_file():raise StackError('Original painted GIF and source art ZIP are mandatory')
    html,meta=package(srczip,a.scene,engine,out/'living_scene_sprite_stacking_3d.html')
    license_path=Path(__file__).resolve().parent.parent/'references'/'LICENSE.threejs.txt'
    if not license_path.is_file():raise StackError('Authoritative Three.js MIT source notice required')
    result=out/'living_scene_sprite_stacking_3d.zip'
    if result.exists():raise StackError('3D browser ZIP already exists; use clean output directory')
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_sprite_stacking_3d/index.html')
        z.write(license_path,'living_scene_sprite_stacking_3d/LICENSE.threejs.txt')
    with zipfile.ZipFile(srczip,'a',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        existing=set(z.namelist())
        files=['project/browser/living_scene_sprite_stacking_3d.zip','project/licenses/LICENSE.threejs.txt']
        if any(x in existing for x in files):raise StackError('Sprite Stacking already present in original source ZIP')
        z.write(result,files[0]);z.write(license_path,files[1])
        z.writestr('project/sprite_stacking/stack_manifest.json',json.dumps(meta,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(srczip) as z:
        if z.testzip():raise StackError('Original source pose ZIP damaged')
    print(json.dumps({'html':str(html),'browser_zip':str(result),'assets_zip':str(srczip),**meta},ensure_ascii=False))

if __name__=='__main__':main()
