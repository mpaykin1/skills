#!/usr/bin/env python3
"""Full source-validated 2.5D stage -> additive offline Howler.js audio player.

Existing GIF/APNG, original PNG ZIP, Godot/Blender and PixiJS variants are retained.
No audio asset or engine is fabricated when external dependencies are absent.
"""
from __future__ import annotations
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
from howler_vendor import vendor
from howler_bridge import make_html,howler_bundle,HowlerBridgeError

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
    for k in ('pixi-js','pathfinding-js','viewport-js','filters-js','particles-js','tilemap-js','howler-js'):
        p.add_argument('--'+k,type=Path)
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters',
              'fetch-particles','fetch-tilemap','fetch-howler','preflight-only'):
        p.add_argument('--'+k,action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    soundjs=a.howler_js
    if not a.preflight_only:
        if soundjs is None and a.fetch_howler:soundjs=vendor(out/'vendor/howler.min.js')
        howler_bundle(soundjs)  # fail BEFORE costly animation render
    predecessor=Path(__file__).resolve().with_name('pixi_culling_delivery.py')
    cmd=[sys.executable,str(predecessor),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
        '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),'--max-width',str(a.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender',
              'pixi-js','pathfinding-js','viewport-js','filters-js','particles-js','tilemap-js'):
        v=getattr(a,k.replace('-','_'))
        if v is not None:cmd.extend(['--'+k,str(v)])
    for k in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters',
              'fetch-particles','fetch-tilemap','preflight-only'):
        if getattr(a,k.replace('-','_')):cmd.append('--'+k)
    status=subprocess.run(cmd,check=False)
    if status.returncode:raise SystemExit(status.returncode)
    if a.preflight_only:return
    origzip=out/'living_scene_assets.zip';origgif=out/'living_scene.gif'
    upstream=out/'living_scene_pixi_culled.html'
    if not all(p.is_file() for p in (origzip,origgif,upstream)):
        raise HowlerBridgeError('Verified original scene GIF + assets ZIP + camera/culling HTML are required')
    html,assets,info=make_html(upstream,out/'living_scene_pixi_audio.html',origzip,a.scene,soundjs)
    lic=Path(__file__).resolve().parent.parent/'references'/'LICENSE.howler.md'
    if not lic.is_file():raise HowlerBridgeError('MIT howler source license missing')
    package=out/'living_scene_pixi_audio.zip'
    if package.exists():raise HowlerBridgeError('Sound export already exists; use a clean output folder')
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_pixi_audio/index.html')
        z.write(lic,'living_scene_pixi_audio/LICENSE.howler.md')
        z.writestr('living_scene_pixi_audio/source_audio.json',json.dumps(info,ensure_ascii=False,indent=2))
        for member,payload in assets:z.writestr('living_scene_pixi_audio/'+member,payload)
    with zipfile.ZipFile(origzip,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        additions={'project/browser/living_scene_pixi_audio.zip':package.read_bytes(),
                   'project/licenses/LICENSE.howler.md':lic.read_bytes(),**dict(assets)}
        old=set(z.namelist())
        if any(m in old for m in additions):raise HowlerBridgeError('Already exported original audio files')
        for name,payload in additions.items():z.writestr(name,payload)
    with zipfile.ZipFile(origzip) as z:
        if z.testzip() is not None:raise HowlerBridgeError('Original asset ZIP corrupted by sound export')
    print(json.dumps({'audio_html':str(html),'audio_zip':str(package),'assets_zip':str(origzip),
                      **info},ensure_ascii=False))

if __name__=='__main__':main()
