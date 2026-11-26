#!/usr/bin/env python3
"""Additive FFmpeg MP4/WebM export after mandatory verified original GIF/ZIP.

Retains unchanged all source PNG cels, alpha APNG/WebP export stages,
Godot/Blender, PixiJS/Howler camera/physics/atmosphere stage entrypoints.
Do not imply that a linear video contains interactive 3D Howler sound.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from ffmpeg_video_bridge import build,VideoBridgeError,check_ffmpeg


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--fps',type=int,default=24);p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--max-width',type=int,default=720)
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+k)
    p.add_argument('--format',choices=('mp4','webm','both'),default='both')
    p.add_argument('--with-ambience',action='store_true')
    p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    types=('mp4','webm') if a.format=='both' else (a.format,)
    if not a.preflight_only:check_ffmpeg(a.ffmpeg,a.ffprobe,types)
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    upstream=Path(__file__).with_name('blender_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--fps',str(a.fps),'--seconds',str(a.seconds),'--max-width',str(a.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        val=getattr(a,k.replace('-','_'))
        if val:cmd.extend(['--'+k,val])
    if a.preflight_only:cmd.append('--preflight-only')
    result=subprocess.run(cmd,check=False)
    if result.returncode:raise SystemExit(result.returncode)
    if a.preflight_only:return
    sourcezip=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    if not sourcezip.is_file() or not gif.is_file():
        raise VideoBridgeError('Original approved GIF and source ZIP were not generated')
    report=build(gif,sourcezip,a.scene,out,a.fps,a.seconds,a.format,a.with_ambience,a.ffmpeg,a.ffprobe)
    license_path=Path(__file__).resolve().parent.parent/'references'/'LICENSE.ffmpeg.txt'
    if not license_path.is_file():raise VideoBridgeError('FFmpeg upstream licensing summary missing')
    archive=out/'living_scene_video.zip'
    if archive.exists():raise VideoBridgeError('Video export exists; use an empty output directory')
    metadata={k:v for k,v in report.items() if k!='original_audio_assets'}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for rec in report['files']:
            source=Path(rec['path'])
            z.write(source,'living_scene_video/'+source.name)
        z.writestr('living_scene_video/config.json',json.dumps(metadata,ensure_ascii=False,indent=2))
        z.write(license_path,'living_scene_video/LICENSE.ffmpeg.txt')
    with zipfile.ZipFile(sourcezip,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        add={'project/video/living_scene_video.zip':archive.read_bytes(),
             'project/licenses/LICENSE.ffmpeg.txt':license_path.read_bytes()}
        for name,content in report['original_audio_assets']:
            add[name]=content
        exists=set(z.namelist())
        for name,payload in add.items():
            if name in exists:
                if z.read(name)!=payload:raise VideoBridgeError('Original asset conflict at '+name)
                continue
            z.writestr(name,payload)
    with zipfile.ZipFile(sourcezip) as z:
        if z.testzip() is not None:raise VideoBridgeError('Source ZIP damaged by video export')
    print(json.dumps({'video_zip':str(archive),'source_zip':str(sourcezip),
         'videos':[f['path'] for f in report['files']],
         'original_motion_gate_retained':True,'character_deformation':False},ensure_ascii=False))

if __name__=='__main__':main()
