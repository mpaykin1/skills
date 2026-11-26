#!/usr/bin/env python3
"""Add genuine Rhubarb full-body viseme speech to *real prior* Howler 2.5D HTML.

Runs all previous original 2D/2.5D identity/action/pose gates, Tiled, A*,
Godot/Blender, PixiJS tilemap/culling and spatial Howler first. Output is
ADDITIVE only; source GIF/PNG/APNG/WebP/video/physics/joystick entrypoints remain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from rhubarb_lipsync_bridge import cli,load_tracks,html_patch,LipSyncError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--fps',type=int,default=24);p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--max-width',type=int,default=720)
    p.add_argument('--rhubarb',default='rhubarb',help='Real official Rhubarb Lip Sync 1.14.0 executable')
    p.add_argument('--ffmpeg',default='ffmpeg',help='Real FFmpeg for original MP3 speech input conversion')
    for opt in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+opt)
    for opt in ('pixi-js','pathfinding-js','viewport-js','filters-js','particles-js','tilemap-js','howler-js'):
        p.add_argument('--'+opt,type=Path)
    for opt in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','fetch-tilemap',
                'fetch-howler','preflight-only'):
        p.add_argument('--'+opt,action='store_true')
    a=p.parse_args()
    if not 24<=a.fps<=120 or not 40<=a.seconds<=60:p.error('Original 24+fps and 40–60s animation must remain')
    if not a.source.is_file() or not a.scene.is_file():p.error('Authentic source image and scene JSON are required')
    if not a.preflight_only:cli(a.rhubarb) # Fail before full upstream render if native tool missing.
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    upstream=Path(__file__).with_name('howler_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),'--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender',
                'pixi-js','pathfinding-js','viewport-js','filters-js','particles-js','tilemap-js','howler-js'):
        val=getattr(a,key.replace('-','_'))
        if val is not None:cmd.extend(['--'+key,str(val)])
    for key in ('fetch-pixi','fetch-pathfinding','fetch-viewport','fetch-filters','fetch-particles','fetch-tilemap',
                'fetch-howler','preflight-only'):
        if getattr(a,key.replace('-','_')):cmd.append('--'+key)
    status=subprocess.run(cmd,check=False)
    if status.returncode:raise SystemExit(status.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip'; audio_html=out/'living_scene_pixi_audio.html'
    if any(not p.is_file() for p in (approved,audio_html,out/'living_scene.gif')):
        raise LipSyncError('Previous verified GIF/asset ZIP and genuine Howler offline HTML required')
    tracks,art,meta=load_tracks(approved,a.scene,a.rhubarb,a.ffmpeg,a.fps)
    html,html_meta=html_patch(audio_html,out/'living_scene_pixi_lipsync.html',tracks)
    lic=Path(__file__).parent.parent/'references/LICENSE.rhubarb-lip-sync.md'
    if not lic.is_file():raise LipSyncError('Original upstream Rhubarb MIT license missing')
    package=out/'living_scene_lipsync.zip'
    if package.exists():raise LipSyncError('Lip sync package already exists; select an empty output directory')
    manifest={'speaker_count':len(tracks),'tracks':[{
        k:v for k,v in t.items() if k not in ('variants',)
    } for t in tracks],**meta,**html_meta}
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.write(html,'living_scene_lipsync/index.html')
        z.write(lic,'living_scene_lipsync/LICENSE.rhubarb-lip-sync.md')
        z.writestr('living_scene_lipsync/timing.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        for name,blob in art:z.writestr('living_scene_lipsync/'+name,blob)
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        names={'project/browser/living_scene_lipsync.zip','project/licenses/LICENSE.rhubarb-lip-sync.md',
               'project/lipsync/cues.json'}
        names.update(k for k,_ in art)
        if any(k in z.namelist() for k in names):
            raise LipSyncError('Duplicate original source lip sync archive entries')
        z.write(package,'project/browser/living_scene_lipsync.zip')
        z.write(lic,'project/licenses/LICENSE.rhubarb-lip-sync.md')
        z.writestr('project/lipsync/cues.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        for name,blob in art:z.writestr(name,blob)
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise LipSyncError('Original actor asset ZIP damaged')
    print(json.dumps({'html':str(html),'lipsync_zip':str(package),'approved_assets_zip':str(approved),
        'original_gif':str(out/'living_scene.gif'),**meta,**html_meta},ensure_ascii=False))

if __name__=='__main__':main()
