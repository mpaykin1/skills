#!/usr/bin/env python3
"""libwebp lossless animated WebP from motion-approved, ORIGINAL PNG pose frames.

CPU-only. Uses the *real* libwebp animation encoder and decoder exposed by
Pillow, or optionally the official img2webp CLI. No simulated WebP bytes,
character changes, or bypass of the existing scene and identity gates.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import numpy as np
from PIL import Image, features, WebPImagePlugin
from pixijs_bridge import load_scene


class WebPBridgeError(ValueError):
    pass


def refuse(message):
    raise WebPBridgeError('libwebp export blocked: ' + str(message))


def name_safe(v):
    if not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', v):
        refuse('Unsafe actor/action ID; use ASCII letters, numbers, _ or -')
    return v


def backend_version():
    if not features.check('webp') or not hasattr(WebPImagePlugin._webp, 'WebPAnimEncoder'):
        refuse('Pillow is missing the authentic libwebp animation encoder/decoder')
    ver = features.version('webp')
    if not ver or not re.match(r'^\d+\.\d+', ver):
        refuse('Cannot verify native libwebp version')
    return ver


def frame_delays(count, fps):
    """Integer-ms, cumulative-error-balanced timestamps (24 FPS => 42,41,42...)."""
    if type(count) is not int or not 2 <= count <= 1500 or type(fps) is not int or not 24 <= fps <= 120:
        refuse('Invalid frame rate/count')
    boundaries = [(2 * k * 1000 + fps) // (2 * fps) for k in range(count + 1)]
    durations = [boundaries[i+1] - boundaries[i] for i in range(count)]
    if min(durations) < 1 or max(durations) > 1000:
        refuse('Frame duration not representable as milliseconds')
    return durations


def authentic_pngs(raws, size):
    if not 2 <= len(raws) <= 1500 or not isinstance(size, tuple) or len(size) != 2:
        refuse('Original full-pose clip/canvas invalid')
    w, h = size
    if min(w,h) < 8 or w*h > 5_000_000: refuse('Oversized or invalid source sprite')
    if len(raws) * w * h * 4 > 128 * 1024 * 1024:
        refuse('CPU memory budget exceeded for lossless full-cel WebP; split original actors/actions')
    result = []
    for i, raw in enumerate(raws):
        if not isinstance(raw, bytes) or not 10 <= len(raw) <= 15_000_000:
            refuse('Invalid original PNG bytes')
        with Image.open(io.BytesIO(raw)) as png:
            if png.format != 'PNG' or png.size != size:
                refuse(f'Original pose PNG canvas mismatch at frame {i}')
            rgba = png.convert('RGBA')
            amin, amax = rgba.getchannel('A').getextrema()
            if amin == 255 or amax == 0:
                refuse(f'Original pose lacks true silhouette alpha at frame {i}')
            result.append(rgba)
    return result


def official_img2webp(binary):
    if binary is None: return None
    candidate = shutil.which(str(binary))
    if candidate is None: refuse('Real official libwebp img2webp binary unavailable')
    probe = subprocess.run([candidate, '-version'], capture_output=True, text=True, timeout=10, check=False)
    if probe.returncode != 0 or not re.search(r'\d+\.\d+', probe.stdout+' '+probe.stderr):
        refuse('img2webp -version failed; refusing unknown encoder')
    return candidate


def verify_animation(path, source_frames, durations):
    """Verify original-visible RGBA at every ORIGINAL timestamp midpoint.

    A legal optimized animation may coalesce identical consecutive frames;
    comparing output-frame count to input-frame count would be incorrect.
    """
    duration_total = sum(durations)
    with Image.open(path) as image:
        if image.format != 'WEBP' or getattr(image, 'n_frames', 1) < 2:
            refuse('Encoder returned static or non-WebP result')
        if image.info.get('loop') != 0:
            refuse('Animation is not configured to loop forever')
        if image.size != source_frames[0].size:
            refuse('Animated WebP canvas does not match original poses')
        timeline = []
        for index in range(image.n_frames):
            image.seek(index)
            image.load()  # native libwebp publishes timestamp/duration on load
            start, span = image.info.get('timestamp'), image.info.get('duration')
            if not isinstance(start, (int,float)) or not isinstance(span,(int,float)):
                refuse('Decoded WebP frame does not expose timestamps')
            if not math.isfinite(start) or not math.isfinite(span) or span < 1:
                refuse('Invalid decoded animation duration')
            rgba = np.asarray(image.convert('RGBA'), dtype=np.uint8).copy()
            if timeline and abs(float(start)-(timeline[-1][0]+timeline[-1][1])) > 1:
                refuse('WebP output has a playback timing gap')
            timeline.append((float(start),float(span),rgba))
    if abs(timeline[-1][0] + timeline[-1][1] - duration_total) > 1:
        refuse('Total playback duration differs from original frame timestamps')
    pointer = 0
    passed = 0
    cursor = 0
    for i, (frame, delay) in enumerate(zip(source_frames, durations)):
        midpoint = cursor + delay / 2
        cursor += delay
        while pointer + 1 < len(timeline) and midpoint >= timeline[pointer][0] + timeline[pointer][1]:
            pointer += 1
        start, span, rgba = timeline[pointer]
        if not start <= midpoint < start + span:
            refuse(f'No decoded WebP pose at source frame midpoint {i}')
        source = np.asarray(frame, dtype=np.uint8)
        if not np.array_equal(source[:,:,3], rgba[:,:,3]):
            refuse(f'Libwebp changed source actor transparency at frame {i}')
        visible = source[:,:,3] != 0
        if not np.array_equal(source[:,:,:3][visible], rgba[:,:,:3][visible]):
            refuse(f'Libwebp changed visible source actor RGB at frame {i}')
        passed += 1
    return {'decoded_keyframes':len(timeline), 'source_frames_verified':passed, 'total_duration_ms':duration_total}


def encode_clip(originals, sprite_size, fps, destination, *, img2webp=None):
    """Animated lossless WebP; no palette conversion, lossy mode or alpha removal."""
    frames = authentic_pngs(originals, sprite_size)
    durations = frame_delays(len(frames), fps)
    if destination.exists(): refuse('Refusing to overwrite an existing animation')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lia_libwebp_') as tmpdir:
        root=Path(tmpdir);temp=root/'animation.webp'
        if img2webp is None:
            version = backend_version()
            # Pillow's built-in WebP animation driver calls the REAL native
            # libwebp encoder. This path is CPU-only, needs no GPU/npm/net.
            frames[0].save(temp, format='WEBP', save_all=True,
                append_images=frames[1:], duration=durations,
                lossless=True, quality=100, alpha_quality=100,
                method=6, minimize_size=True, allow_mixed=False,
                background=(0,0,0,0), loop=0)
            encoder='Pillow native libwebp '+version
        else:
            cli = official_img2webp(img2webp)
            argv=[cli,'-loop','0','-lossless','-exact','-m','6']
            for i,(blob,dur) in enumerate(zip(originals,durations)):
                path=root/f'{i:05d}.png';path.write_bytes(blob)
                argv.extend(['-d',str(dur),str(path)])
            argv.extend(['-o',str(temp)])
            try:
                p=subprocess.run(argv,capture_output=True,text=True,timeout=360,check=False)
            except (OSError,subprocess.TimeoutExpired) as ex:
                refuse('Real img2webp encoder failed: '+str(ex))
            if p.returncode != 0: refuse('Real img2webp rejected source: '+(p.stderr or p.stdout)[-550:])
            encoder='official libwebp img2webp'
        if not temp.is_file() or not 0 < temp.stat().st_size <= 100_000_000:
            refuse('No usable animated WebP was produced')
        check=verify_animation(temp,frames,durations)
        shutil.copyfile(temp,destination)
    return {'frames':len(frames),'duration_ms':sum(durations),
        'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
        'source_frames_sha256':[hashlib.sha256(b).hexdigest() for b in originals],
        'encoder':encoder,'lossless':True, 'alpha_preserved':True,
        **check}


def build(approved_zip, destination, fps=24, per_action=False, img2webp=None):
    approved_zip=Path(approved_zip).resolve();destination=Path(destination).resolve()
    if type(per_action) is not bool or type(fps) is not int or not 24 <= fps <= 120:
        refuse('Invalid output settings')
    if img2webp is None:backend_version()
    else:official_img2webp(img2webp)
    approved=load_scene(approved_zip)  # mandatory existing original identity+pose gate
    if destination.exists() and any(destination.iterdir()):
        refuse('WebP output directory must be empty')
    destination.mkdir(parents=True,exist_ok=True)
    result=[];roster=[]
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:refuse('Original complete GIF/ZIP corrupted')
        cfg=json.loads(z.read('scene.json'))
        if json.loads(z.read('motion_gate.json')).get('all_actors_pass') is not True:
            refuse('Full original character motion gate failed')
        for actor in cfg.get('actors',[]):
            aid=name_safe(actor['id'])
            if aid in roster:refuse('Duplicate source actor ID')
            roster.append(aid)
            size=tuple(actor['box'][2:4])
            clip_names=set();all_frames=[]
            for clip in actor['clips']:
                action=name_safe(clip['action'])
                if action=='complete_cycle' or action in clip_names:
                    refuse('Duplicate or reserved action in original scene')
                clip_names.add(action)
                blobs=[]
                for frame in clip['frames']:
                    relative=frame.get('png')
                    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or relative.startswith('/') or any(n in ('.','..','') for n in relative.split('/')):
                        refuse('Unsafe source pose PNG path')
                    try:raw=z.read('project/inputs/'+relative)
                    except KeyError:refuse('Approved original pose PNG missing: '+relative)
                    blobs.append(raw)
                if len(blobs)<12:refuse('Missing validated source action frames')
                all_frames.extend(blobs)
                if per_action:
                    relative=f'actors/{aid}/{action}.webp'
                    output=encode_clip(blobs,size,fps,destination/relative,img2webp=img2webp)
                    result.append({'actor':aid,'action':action,'path':relative,**output})
            relative=f'actors/{aid}/complete_cycle.webp'
            output=encode_clip(all_frames,size,fps,destination/relative,img2webp=img2webp)
            result.append({'actor':aid,'action':'complete_cycle','path':relative,**output})
    if set(roster)!={a['id'] for a in approved['actors']}:
        refuse('Original certified character inventory changed')
    report={'format':'animated-WebP','encoder':'native libwebp','source':'original approved independent RGBA cels',
        'fps':fps,'loops':0,'actor_count':len(roster),'files':result,
        'source_gate':'motion_gate.json.all_actors_pass=true',
        'lossless':True,'character_deformation':False,'gpu_required':False}
    (destination/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--approved-zip',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--per-action',action='store_true')
    p.add_argument('--img2webp',help='Optional actual official libwebp img2webp CLI; default uses Pillow native libwebp')
    a=p.parse_args()
    result=build(a.approved_zip,a.out,a.fps,a.per_action,a.img2webp)
    print(json.dumps({'webp_count':len(result['files']),'actors':result['actor_count'],
        'output':str(a.out)},ensure_ascii=False))
