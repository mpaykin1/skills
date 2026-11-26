#!/usr/bin/env python3
"""One complete delivery: all previous image/pose gates, then Godot 4 scene.

Never bypasses ControlNet Aux, SAM 2, MMPose, DeepLabCut, Krita,
OpenToonz, Pixelorama, or native full-frame pose-sequence validation.
"""
from __future__ import annotations
import argparse
import json
import io
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image
from godot_bridge import compile_project,GodotBridgeError
from tiled_bridge import apply_tiled
from ldtk_bridge import apply_ldtk


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path)
    ap.add_argument('--scene',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seconds',type=int,default=48)
    ap.add_argument('--fps',type=int,default=24)
    ap.add_argument('--max-width',type=int,default=720)
    ap.add_argument('--pixelorama')
    ap.add_argument('--opentoonz')
    ap.add_argument('--mmpose-device')
    ap.add_argument('--comfyui-url')
    ap.add_argument('--godot',help='Optional installed Godot 4 binary for headless editor import check')
    ap.add_argument('--preflight-only',action='store_true')
    a=ap.parse_args()
    if a.fps<24:
        ap.error('Frame-based character animation needs at least 24 FPS')
    out=a.out.resolve();scene=a.scene.resolve()
    cmd=[sys.executable,str(Path(__file__).with_name('controlnet_aux_delivery.py')),
         str(a.source.resolve()),'--scene',str(scene),'--out',str(out),
         '--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for option,value in [('pixelorama',a.pixelorama),('opentoonz',a.opentoonz),
                         ('mmpose-device',a.mmpose_device),('comfyui-url',a.comfyui_url)]:
        if value:cmd.extend(['--'+option,value])
    if a.preflight_only:cmd.append('--preflight-only')
    completed=subprocess.run(cmd,check=False)
    if completed.returncode:raise SystemExit(completed.returncode)
    if a.preflight_only:return
    source_zip=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    if not source_zip.is_file() or not gif.is_file():
        raise GodotBridgeError('Original full-pose GIF/ZIP failed validation; cannot create Godot export')
    # Preserve author-supplied original full-resolution foreground plates even
    # after .tnz/.pxo compilers relocate scene.json to an intermediate folder.
    source_scene=json.loads(scene.read_text('utf8'))
    extra_layers=source_scene.get('godot',{}).get('layers',[])
    if extra_layers:
        with zipfile.ZipFile(source_zip,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            previous=set(z.namelist())
            with Image.open(a.source.resolve()) as original:
                original_dimensions=original.size
            for plane in extra_layers:
                raw=plane.get('png') if isinstance(plane,dict) else None
                if not isinstance(raw,str) or not raw or Path(raw).is_absolute() or '\\' in raw or any(v in ('.','..','') for v in raw.split('/')):
                    raise GodotBridgeError('Original foreground layer path must be safe and scene-relative')
                imgpath=(scene.parent/raw).resolve()
                if scene.parent not in imgpath.parents or not imgpath.is_file():
                    raise GodotBridgeError('Required original 2.5D plane missing '+raw)
                with Image.open(imgpath) as img:
                    if img.format!='PNG' or img.size!=original_dimensions:
                        raise GodotBridgeError('Foreground art must be source-registered PNG '+raw)
                member='project/inputs/'+raw
                if member not in previous:
                    z.write(imgpath,member)
                    previous.add(member)
    # Tiled authored map annotations enrich only verified source scene metadata.
    # The original GIF, pose images and motion_gate.json stay byte-identical.
    apply_tiled(source_zip,scene,a.source.resolve())
    # LDtk enhances Tiled navigation and foreground layers without rewriting poses.
    apply_ldtk(source_zip,scene,a.source.resolve())
    package,metadata=compile_project(source_zip,out,a.godot, fps=a.fps)
    with zipfile.ZipFile(source_zip,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        name='project/godot/living_scene_godot.zip'
        if name in z.namelist():
            raise GodotBridgeError('Godot package already exists in assets ZIP; refusing duplicate entry')
        z.write(package,name)
        z.writestr('godot_integration.json',json.dumps({
            'bridge':'godot-4-authentic-cels','frame_rate':a.fps,
            'engine_installed_and_checked':bool(a.godot),
            'timeline_mode':'same authored source-pixel world path as validated GIF',
            'navigation_mode':'optional real NavigationAgent2D + CharacterBody2D; authored walkable polygons required',
            'character_deformation':False,**metadata},ensure_ascii=False,indent=2))
    with zipfile.ZipFile(source_zip) as z:
        if z.testzip() is not None:raise GodotBridgeError('Final ZIP damaged')
    print(json.dumps({'gif':str(gif),'assets_zip':str(source_zip),
                      'godot_zip':str(package),**metadata},ensure_ascii=False))

if __name__=='__main__':main()
