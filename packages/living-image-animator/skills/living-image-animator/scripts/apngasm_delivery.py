#!/usr/bin/env python3
"""Entire original native cel->GIF/ZIP->Godot/Blender gate then original apngasm APNGs.

The APNG stage is additive: all editor sources and original GIF remain.
Browser users can embed the APNG files in an offline HTML without CDN/GL.
"""
from __future__ import annotations
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
from apngasm_bridge import build,tool_path,APNGAsmError
from apngasm_install import install


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    for opt in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+opt)
    p.add_argument('--apngasm',help='Actual externally installed apngasm 3.x CLI')
    p.add_argument('--build-apngasm',action='store_true',help='CPU-only build official source with git/CMake when network is available')
    p.add_argument('--per-action',action='store_true',help='Extra separate transparent APNG for every original action')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    apngasm=a.apngasm
    if not a.preflight_only:
        if apngasm is None and a.build_apngasm:
            apngasm=str(install(out/'vendor/apngasm'))
        tool_path(apngasm)  # abort BEFORE expensive upstream GIF render
    upstream=Path(__file__).resolve().with_name('blender_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),'--scene',str(a.scene.resolve()),
         '--out',str(out),'--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for k in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        value=getattr(a,k.replace('-','_'))
        if value:cmd.extend(['--'+k,str(value)])
    if a.preflight_only:cmd.append('--preflight-only')
    proc=subprocess.run(cmd,check=False)
    if proc.returncode:raise SystemExit(proc.returncode)
    if a.preflight_only:return
    assetzip=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    if not assetzip.is_file() or not gif.is_file():
        raise APNGAsmError('Original full-cel GIF/ZIP did not complete all prior validations')
    output=out/'living_scene_apng'
    manifest=build(assetzip,output,apngasm,a.fps,a.per_action)
    license_path=Path(__file__).parent.parent/'references'/'LICENSE.apngasm.txt'
    if not license_path.is_file():raise APNGAsmError('Original license attribution missing')
    pack=out/'living_scene_apng.zip'
    if pack.exists():raise APNGAsmError('APNG output already exists; use a fresh directory')
    with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(output.rglob('*')):
            if file.is_file():z.write(file,('living_scene_apng/'+file.relative_to(output).as_posix()))
        z.write(license_path,'living_scene_apng/LICENSE.apngasm.txt')
    with zipfile.ZipFile(assetzip,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        if 'project/apng/living_scene_apng.zip' in z.namelist():
            raise APNGAsmError('Duplicate APNG package; do not reuse an existing output directory')
        z.write(pack,'project/apng/living_scene_apng.zip')
        z.write(license_path,'project/licenses/LICENSE.apngasm.txt')
    with zipfile.ZipFile(assetzip) as z:
        if z.testzip() is not None:raise APNGAsmError('Final original ZIP became corrupt')
    print(json.dumps({'original_gif':str(gif),'original_assets_zip':str(assetzip),
      'transparent_apng_zip':str(pack),'actor_count':manifest['actor_count'],
      'apng_count':len(manifest['files'])},ensure_ascii=False))

if __name__=='__main__':main()
