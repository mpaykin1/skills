#!/usr/bin/env python3
"""Authentic apngasm 3.x -> original alpha-preserving full-cel actor APNG loops.

Consumes only the already-approved v3 scene ZIP. Frames are always extracted
from original PNG bytes, never rendered/interpolated from a still image or GIF.
External C++ apngasm is mandatory; every APNG is decoded and pixel-checked.
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
from PIL import Image
from pixijs_bridge import load_scene

class APNGAsmError(ValueError):
    pass


def reject(s):
    raise APNGAsmError('apngasm export blocked: ' + str(s))


def safe_name(s):
    if not isinstance(s,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', s):
        reject('Unsafe or non-unique actor/action identifier; use ASCII IDs')
    return s


def tool_path(candidate=None):
    name = str(candidate or os.environ.get('APNGASM_BIN') or 'apngasm')
    path = shutil.which(name)
    if not path:
        reject('Authentic apngasm 3.x CLI is not installed; supply --apngasm or APNGASM_BIN')
    try:
        result = subprocess.run([path,'--version'],capture_output=True,text=True,timeout=10,check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        reject('Cannot inspect apngasm executable: '+str(exc))
    version = (result.stdout+' '+result.stderr).strip()
    if result.returncode!=0 or not re.search(r'apngasm|APNG\s+Assembler',version,re.I) or not re.search(r'(?<!\d)3(?:\.\d+)+',version):
        reject('Expected supported apngasm 3.x CLI, got '+version[:160])
    return path, version[:160]


def encode_loop(cli, originals: list[bytes], size:tuple[int,int], fps:int, destination:Path):
    if not 2<=len(originals)<=1500:reject('Original loop has invalid frame count')
    if not 24<=fps<=120:reject('Only authored 24..120 FPS allowed')
    if size[0]*size[1]>5_000_000:reject('Actor atlas/canvas exceeds APNG budget')
    source=[]
    with tempfile.TemporaryDirectory(prefix='lia_apngasm_') as td:
        root=Path(td)
        for i,raw in enumerate(originals):
            if len(raw)>15_000_000:reject('Oversized original pose PNG')
            with Image.open(io.BytesIO(raw)) as img:
                if img.format!='PNG' or img.size!=size:reject('Original PNG canvas mismatch')
                rgba=img.convert('RGBA')
                a=rgba.getchannel('A').getextrema()
                if a[0]==255 or a[1]==0:reject('Expected true transparent nonempty original cel')
                source.append(rgba)
            file=root/f'{i:05d}.png';file.write_bytes(raw)
        tmp=root/'combined.png'
        cmd=[cli,*[str(root/f'{i:05d}.png') for i in range(len(source))],
             '-o',str(tmp),'-d',f'1/{fps}','-l','0','-F']
        try:
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=240,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:
            reject('apngasm process failed: '+str(exc))
        if proc.returncode!=0 or not tmp.is_file():
            reject('apngasm failed: '+(proc.stderr or proc.stdout)[-350:])
        if tmp.stat().st_size>100_000_000:reject('APNG output exceeds 100 MB')
        # apngasm may coalesce identical adjacent frames: compare actual playback
        # at every original frame's temporal midpoint, not only nominal frame count.
        with Image.open(tmp) as anim:
            if anim.format!='PNG' or getattr(anim,'n_frames',1)<2:
                reject('CLI produced static PNG instead of animated PNG')
            if anim.info.get('loop')!=0:reject('Expected seamless infinite loop')
            timeline=[]; cumulative=0.0
            for j in range(anim.n_frames):
                anim.seek(j)
                ms=float(anim.info.get('duration') or 0)
                if not math.isfinite(ms) or ms<=0:reject('Invalid APNG frame duration')
                cumulative+=ms
                timeline.append((cumulative,anim.convert('RGBA').copy()))
            expected_ms=len(source)*1000/fps
            if abs(cumulative-expected_ms)>max(2.0, .002*expected_ms):
                reject(f'APNG duration mismatch {cumulative:.2f}ms vs {expected_ms:.2f}ms')
            k=0
            import numpy as np
            for i,src in enumerate(source):
                when=(i+.5)*1000/fps
                while k<len(timeline)-1 and timeline[k][0]<when: k+=1
                out=timeline[k][1]
                if out.size!=size:reject('Decoded animation has wrong dimensions')
                a=np.array(src,dtype=np.uint8);b=np.array(out,dtype=np.uint8)
                visible=(a[:,:,3]!=0)|(b[:,:,3]!=0)
                if not np.array_equal(a[:,:,3],b[:,:,3]) or not np.array_equal(a[:,:,:3][visible],b[:,:,:3][visible]):
                    reject(f'APNG altered visible source sprite pixels at frame {i}')
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():reject('Refusing to overwrite an existing APNG')
        shutil.copyfile(tmp,destination)
    return {'frames':len(source),'duration_ms':round(expected_ms,3),
            'bytes':destination.stat().st_size,
            'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
            'source_frames_sha256':[hashlib.sha256(v).hexdigest() for v in originals]}


def build(approved_zip, dest, apngasm=None, fps=24, per_action=False):
    approved_zip=Path(approved_zip).resolve();dest=Path(dest).resolve()
    if type(per_action) is not bool:reject('per_action must be bool')
    # Reuse EXACT original upstream PixiJS source frame and motion gate validator.
    verified=load_scene(approved_zip)
    if type(fps) is not int or not 24<=fps<=120:reject('Invalid FPS')
    cli,version=tool_path(apngasm)
    dest.mkdir(parents=True,exist_ok=True)
    if any(dest.iterdir()):reject('Use a fresh APNG output directory')
    actor_ids=set();entry=[]
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:reject('Corrupt original source ZIP')
        scene=json.loads(z.read('scene.json'))
        gate=json.loads(z.read('motion_gate.json'))
        if gate.get('all_actors_pass') is not True:reject('Source GIF/pose gate failed')
        for actor in scene['actors']:
            aid=safe_name(actor['id'])
            if aid in actor_ids:reject('Duplicate actor ID')
            actor_ids.add(aid)
            x,y,w,h=actor['box']
            all_src=[];seen_actions=set()
            clips=actor.get('clips',[])
            if len(clips)<2:reject('Actor has insufficient original actions')
            for clip in clips:
                act=safe_name(clip['action'])
                if act in seen_actions or act=='complete_cycle':reject('Duplicate or reserved actor action')
                seen_actions.add(act)
                pngs=[]
                for frame in clip['frames']:
                    rel=frame.get('png')
                    if not isinstance(rel,str) or rel.startswith('/') or '\\' in rel or ':' in rel or '..' in rel.split('/'):
                        reject('Unsafe original frame path')
                    name='project/inputs/'+rel
                    try:raw=z.read(name)
                    except KeyError:reject('Missing original source PNG '+name)
                    pngs.append(raw)
                if len(pngs)<12:reject('Incomplete genuine full-body clip')
                all_src.extend(pngs)
                if per_action:
                    filename=f'actors/{aid}/{act}.apng'
                    result=encode_loop(cli,pngs,(w,h),fps,dest/filename)
                    entry.append({'actor':aid,'action':act,'path':filename,**result})
            filename=f'actors/{aid}/complete_cycle.apng'
            result=encode_loop(cli,all_src,(w,h),fps,dest/filename)
            entry.append({'actor':aid,'action':'complete_cycle','path':filename,**result})
    if len(actor_ids)!=len(verified['actors']):reject('Actor roster changed')
    meta={'format':'APNG','encoder':'official apngasm 3.x','encoder_version':version,
          'fps':fps,'loops':0,'actor_count':len(actor_ids),'files':entry,
          'source':'original verified full-body PNG cels','deformation':False,
          'upstream_gate':'motion_gate.json.all_actors_pass=true'}
    (dest/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8')
    return meta


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--approved-zip',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--apngasm')
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--per-action',action='store_true')
    a=p.parse_args()
    result=build(a.approved_zip,a.out,a.apngasm,a.fps,a.per_action)
    print(json.dumps({'actor_count':result['actor_count'],'apng_count':len(result['files']),
                      'output':str(a.out)},ensure_ascii=False))
