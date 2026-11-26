#!/usr/bin/env python3
"""Original full-cel art -> original GIF/ZIP/Godot/Blender -> libwebp WebP.

Optionally invokes the existing apngasm delivery *first*, giving both real
APNG and lossless WebP outputs from the same verified source PNG frames.
Every earlier scene, pose, identity, joint, feet, editor and motion gate stays.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from libwebp_bridge import WebPBridgeError, backend_version, build, official_img2webp


def compare_formats(webp_manifest, apng_manifest=None):
    apng = {}
    if apng_manifest:
        for record in apng_manifest.get('files', []):
            apng[(record['actor'], record['action'])] = record
    matches=[]
    for entry in webp_manifest['files']:
        ap=apng.get((entry['actor'],entry['action']))
        wbytes=entry['bytes']
        abytes=ap['bytes'] if ap else None
        smaller='APNG' if ap and abytes < wbytes else 'animated-WebP'
        matches.append({'actor':entry['actor'],'action':entry['action'],
                        'preferred':smaller,'webp_file':entry['path'],'webp_bytes':wbytes,
                        'apng_file':ap['path'] if ap else None,'apng_bytes':abytes,
                        'comparison':'exact original-visible lossless pixels',
                        'character_deformation':False})
    return {'selection':'prefer smallest verified lossless animation; compare actual bytes',
            'webp_encoder':'native libwebp','has_apng_alternative':bool(apng_manifest),'assets':matches}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('--scene', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--seconds', type=int, default=48)
    p.add_argument('--fps', type=int, default=24)
    p.add_argument('--max-width', type=int, default=720)
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        p.add_argument('--'+key)
    p.add_argument('--per-action', action='store_true')
    p.add_argument('--img2webp', help='Optional real official libwebp CLI (Pillow libwebp is default)')
    p.add_argument('--with-apng', action='store_true', help='Also run existing real apngasm and compare format sizes')
    p.add_argument('--apngasm', help='External existing real apngasm 3.x executable')
    p.add_argument('--build-apngasm', action='store_true', help='Build real apngasm source if internet and CMake are installed')
    p.add_argument('--preflight-only', action='store_true')
    a=p.parse_args()
    if a.fps < 24 or a.fps > 120 or not 40 <= a.seconds <= 60:
        p.error('Use source-frame FPS >=24 and 40..60 second loop')
    if (a.apngasm or a.build_apngasm) and not a.with_apng:
        p.error('Use --with-apng when supplying apngasm settings')
    if a.img2webp:official_img2webp(a.img2webp)
    else:backend_version()  # real native libwebp, no GPU/network dependency
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    path=Path(__file__).resolve()
    upstream=path.with_name('apngasm_delivery.py' if a.with_apng else 'blender_delivery.py')
    cmd=[sys.executable,str(upstream),str(a.source.resolve()),
         '--scene',str(a.scene.resolve()),'--out',str(out),
         '--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for key in ('pixelorama','opentoonz','mmpose-device','comfyui-url','godot','blender'):
        val=getattr(a,key.replace('-','_'))
        if val:cmd.extend(['--'+key,str(val)])
    if a.with_apng:
        if a.apngasm:cmd.extend(['--apngasm',a.apngasm])
        if a.build_apngasm:cmd.append('--build-apngasm')
        if a.per_action:cmd.append('--per-action')
    if a.preflight_only:cmd.append('--preflight-only')
    finished=subprocess.run(cmd,check=False)
    if finished.returncode:raise SystemExit(finished.returncode)
    if a.preflight_only:return
    approved=out/'living_scene_assets.zip';original_gif=out/'living_scene.gif'
    if not approved.is_file() or not original_gif.is_file():
        raise WebPBridgeError('Full previous independent-pose GIF and source ZIP are required')
    work=out/'living_scene_webp'
    result=build(approved,work,a.fps,a.per_action,a.img2webp)
    apng_data=None
    if a.with_apng:
        apng_pack=out/'living_scene_apng.zip'
        apng_manifest=out/'living_scene_apng'/'manifest.json'
        if not apng_pack.is_file() or not apng_manifest.is_file():
            raise WebPBridgeError('Requested original apngasm output is missing')
        apng_data=json.loads(apng_manifest.read_text('utf8'))
        if apng_data.get('actor_count')!=result['actor_count'] or apng_data.get('fps')!=a.fps:
            raise WebPBridgeError('APNG and WebP output have different original cast or FPS')
    preferred=compare_formats(result,apng_data)
    (work/'preferred_animated_assets.json').write_text(json.dumps(preferred,ensure_ascii=False,indent=2),'utf8')
    license_file=path.parent.parent/'references'/'LICENSE.libwebp.txt'
    if not license_file.is_file():raise WebPBridgeError('Official libwebp license attribution missing')
    pack=out/'living_scene_webp.zip'
    if pack.exists():raise WebPBridgeError('Existing WebP ZIP; choose a clean output directory')
    with zipfile.ZipFile(pack,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for f in sorted(work.rglob('*')):
            if f.is_file():z.write(f,'living_scene_webp/'+f.relative_to(work).as_posix())
        z.write(license_file,'living_scene_webp/LICENSE.libwebp.txt')
    with zipfile.ZipFile(approved,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        member='project/webp/living_scene_webp.zip'
        if member in z.namelist():raise WebPBridgeError('WebP artifact already in verified ZIP')
        z.write(pack,member)
        z.write(license_file,'project/licenses/LICENSE.libwebp.txt')
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:raise WebPBridgeError('Output ZIP corrupted')
    print(json.dumps({'original_gif':str(original_gif), 'original_assets_zip':str(approved),
        'lossless_webp_zip':str(pack), 'apng_zip':str(out/'living_scene_apng.zip') if a.with_apng else None,
        'actors':result['actor_count'],'webp_animations':len(result['files']),
        'original_actor_pixels_changed':False,'gpu_required':False},ensure_ascii=False))


if __name__=='__main__':main()
