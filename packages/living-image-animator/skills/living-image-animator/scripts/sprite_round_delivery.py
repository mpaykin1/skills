#!/usr/bin/env python3
"""Full unchanged source pose/GIF/Godot/Blender/Three.js stack chain -> genuine sprite-in-the-round 3D exports.

This is an additive asset output and never claims to run Matter/YUKA or replaces
original Godot/PixiJS/Three.js HTML. The artist original PNGs are packed byte-exact.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from sprite_round_vendor import locate,fetch
from sprite_round_bridge import export_scene,RoundBridgeError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--max-width',type=int,default=720)
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+key)
    p.add_argument('--three-js',type=Path)
    p.add_argument('--fetch-three',action='store_true')
    p.add_argument('--upstream',type=Path,help='Original git-verified sprite-in-the-round source folder')
    p.add_argument('--fetch-round',action='store_true',help='Fetch real pinned upstream source at build time')
    p.add_argument('--turntable',action='store_true')
    p.add_argument('--limit',type=int,default=250)
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    if a.fps<24 or not 40<=a.seconds<=60:p.error('Original full-body 24fps+ and 40–60s gates remain mandatory')
    if not a.source.is_file() or not a.scene.is_file():p.error('Original source and authored scene JSON required')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    upstream=a.upstream
    if not a.preflight_only:
        if upstream is None and a.fetch_round:upstream=fetch(out/'vendor'/'sprite-in-the-round')
        upstream=locate(upstream)
    prev=Path(__file__).resolve().with_name('sprite_stack_delivery.py')
    cmd=[sys.executable,str(prev),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
        '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),'--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        value=getattr(a,key.replace('-','_'))
        if value:cmd.extend(['--'+key,str(value)])
    if a.three_js:cmd.extend(['--three-js',str(a.three_js)])
    if a.fetch_three:cmd.append('--fetch-three')
    if a.preflight_only:cmd.append('--preflight-only')
    done=subprocess.run(cmd,check=False)
    if done.returncode:raise SystemExit(done.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    three=out/'living_scene_sprite_stacking_3d.html'
    if any(not x.is_file() for x in (approved,gif,three)):
        raise RoundBridgeError('Original GIF, source ZIP, Three.js sprite stack HTML must all exist before new asset export')
    result=export_scene(approved,a.scene,out/'sprite_in_the_round',upstream,turntable=a.turntable,limit=a.limit)
    lic=upstream/'LICENSE'
    target=out/'living_scene_sprite_in_the_round.zip'
    if target.exists():raise RoundBridgeError('New asset ZIP path exists; choose fresh output')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted((out/'sprite_in_the_round').rglob('*')):
            if file.is_file():z.write(file,'sprite_in_the_round/'+file.relative_to(out/'sprite_in_the_round').as_posix())
        z.write(lic,'sprite_in_the_round/LICENSE.sprite-in-the-round.txt')
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise RoundBridgeError('Exported sprite-in-the-round ZIP corrupted')
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        member='project/sprite_stacking/living_scene_sprite_in_the_round.zip'
        if member in z.namelist():raise RoundBridgeError('This asset export already present in original source ZIP')
        z.write(target,member)
    with zipfile.ZipFile(approved) as z:
        if z.testzip():raise RoundBridgeError('Original source assets ZIP damaged')
    print(json.dumps({'asset_pack':str(target),'full_source_zip':str(approved),
        'original_gif':str(gif),'original_threejs_viewer':str(three),
        'models':len(result['assets']),'source_unchanged':True},ensure_ascii=False))

if __name__=='__main__':main()
