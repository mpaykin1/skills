#!/usr/bin/env python3
"""Original strict 2D/2.5D animation->PixiJS atlas+viewport->pixi-filters plates.

Additive: original 40-60 s GIF, source ZIP, Godot, Blender, original PixiJS and
pixi-viewport builds are preserved. No filter can touch original actor cels.
"""
from __future__ import annotations
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
from pixi_filters_vendor import vendor
from pixi_filters_bridge import patch_html,vendor_bundle,FiltersBridgeError

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48);p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+k)
    for k in ('pixi-js','pathfinding-js','viewport-js','filters-js'):
        p.add_argument('--'+k,type=Path)
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','preflight-only'):
        p.add_argument('--'+k,action='store_true')
    args=p.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    fbin=args.filters_js
    if not args.preflight_only:
        if args.fetch_filters and fbin is None:fbin=vendor(out/'vendor/pixi-filters.min.js')
        vendor_bundle(fbin) # validate dependency before expensive upstream render
    upstream=Path(__file__).with_name('pixi_viewport_delivery.py')
    cmd=[sys.executable,str(upstream),str(args.source.resolve()),'--scene',str(args.scene.resolve()),
         '--out',str(out),'--seconds',str(args.seconds),'--fps',str(args.fps),'--max-width',str(args.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender','pixi-js','pathfinding-js','viewport-js'):
        value=getattr(args,key.replace('-','_'))
        if value:cmd.extend(['--'+key,str(value)])
    for key in ('fetch-pixi','fetch-pathfinding','fetch-viewport','preflight-only'):
        if getattr(args,key.replace('-','_')):cmd.append('--'+key)
    result=subprocess.run(cmd,check=False)
    if result.returncode:raise SystemExit(result.returncode)
    if args.preflight_only:return
    approved=out/'living_scene_assets.zip'
    viewport=out/'living_scene_pixi_viewport.html'
    if not approved.is_file() or not viewport.is_file():
        raise FiltersBridgeError('Previous approved GIF/ZIP and real viewport HTML must exist')
    html,meta=patch_html(viewport,out/'living_scene_pixi_filters.html',approved,fbin)
    license_path=Path(__file__).parent.parent/'references/LICENSE.pixi-filters.txt'
    if not license_path.is_file():raise FiltersBridgeError('pixi-filters MIT license missing')
    package=out/'living_scene_pixi_filters.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_filters/index.html')
        z.write(license_path,'living_scene_pixi_filters/LICENSE.pixi-filters.txt')
        z.writestr('living_scene_pixi_filters/config.json',json.dumps(meta,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        name='project/browser/living_scene_pixi_filters.zip'
        if name in z.namelist():raise FiltersBridgeError('Duplicate effect artifact in ZIP')
        z.write(package,name)
        z.write(license_path,'project/licenses/LICENSE.pixi-filters.txt')
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise FiltersBridgeError('Output ZIP corrupted')
    print(json.dumps({'filters_html':str(html),'filters_zip':str(package),
       'source_assets_zip':str(approved),**meta},ensure_ascii=False))

if __name__=='__main__':main()
