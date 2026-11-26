#!/usr/bin/env python3
"""Authoritative original sprite stack / original static GLB / Unity source -> offline HTML.

Actual horizontal PNG slices + WebGL2 volume DDA, never fake-depth billboard.
Preserves all inputs. Original game WebGL is the playable route.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
GLB_CONVERT=HERE/'stack_from_glb.py'
UNITY_EXPORT=ROOT/'godot-game-to-html'/'scripts'/'export_unity_glb.py'
THREE='0.187.0'
ESBUILD='0.25.5'
MAX_RAW_BYTES=128*1024*1024
MAX_SCENES=100
MAX_UNIQUE=32


def vec(value, label, positive=False):
    if not isinstance(value,(list,tuple)) or len(value)!=3:
        raise ValueError(f'{label} must contain exactly 3 finite numbers')
    out=[float(v) for v in value]
    if not all(math.isfinite(v) for v in out) or (positive and any(v<=0 for v in out)):
        raise ValueError(f'{label} contains nonfinite/nonpositive values')
    return out


def volume(path:Path)->dict:
    path=path.resolve(strict=True)
    meta=json.loads(path.read_text(encoding='utf8'))
    names=meta.get('layers')
    if not isinstance(names,list) or not 1<=len(names)<=256 or len(names)!=len(set(names)):
        raise ValueError('stack.json must contain 1..256 distinct bottom-to-top PNG slices')
    spacing=vec(meta.get('spacing'), 'spacing',positive=True)
    pivot=vec(meta.get('pivot',[0,0,0]),'pivot')
    w=h=None;total=0;chunks=[];occupied=0
    for name in names:
        if not isinstance(name,str) or not name.lower().endswith('.png'):
            raise ValueError('Every layer must be a PNG file')
        candidate=path.parent/name
        if candidate.is_symlink():raise ValueError('Symlinked slice forbidden')
        f=candidate.resolve(strict=True)
        if path.parent!=f.parent and path.parent not in f.parents:
            raise ValueError('Layer escapes source stack directory')
        with Image.open(f) as im:
            if im.format!='PNG' or im.mode!='RGBA':
                raise ValueError(f'Layer must be real RGBA PNG: {name}')
            if w is None: w,h=im.size
            if im.size!=(w,h):raise ValueError('Layers have different dimensions')
            if w>512 or h>512 or min(w,h)<1:raise ValueError('Slice dimensions outside 1..512')
            rgba=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
            # alpha channel corresponds to occupancy; transparent voxels stay transparent.
            occupied+=sum(a>=128 for a in rgba[3::4])
            chunks.append(rgba);total+=len(rgba)
            if total>MAX_RAW_BYTES:raise ValueError('One stack exceeds 128 MiB RGBA budget')
    if not occupied:raise ValueError('Sprite stack has no opaque volume')
    return {'name':path.parent.name,'dims':[w,h,len(names)],'spacing':spacing,'pivot':pivot,
      'rgba':base64.b64encode(b''.join(chunks)).decode('ascii'),
      'source_sha256':meta.get('source_sha256'),'layers':len(names),'raw_bytes':total}


def parse_sources(source:Path, outdir:Path,xy:int,z:int,allow_shell:bool,unity:str|None,all_scenes:bool):
    source=source.expanduser().resolve(strict=True)
    if source.is_file() and source.suffix.lower()=='.json':
        if source.name=='stack.json' or 'layers' in json.loads(source.read_text(encoding='utf8')):
            return [{'path':source,'position':[0,0,0],'rotation':[0,0,0],'scale':[1,1,1]}]
        doc=json.loads(source.read_text(encoding='utf8'))
        entries=doc.get('stacks')
        if not isinstance(entries,list) or not entries:
            raise ValueError('Scene JSON needs nonempty stacks array')
        if len(entries)>MAX_SCENES:raise ValueError('Too many sprite-stack instances')
        result=[]
        for obj in entries:
            path_str=obj.get('stack')
            if not isinstance(path_str,str):raise ValueError('Each scene item needs stack path')
            p=(source.parent/path_str).resolve(strict=True)
            if p.is_dir():p=p/'stack.json'
            if p.name!='stack.json':raise ValueError('Scene items must refer to stack.json')
            rawframes=obj.get('frames',[])
            if not isinstance(rawframes,list) or len(rawframes)>24:
                raise ValueError('frames must be <=24 distinct authored full-stack pose paths')
            frames=[]
            for raw in rawframes:
                if not isinstance(raw,str):raise ValueError('Frame path must be a string')
                fp=(source.parent/raw).resolve(strict=True)
                if fp.is_dir():fp=fp/'stack.json'
                if fp.name!='stack.json':raise ValueError('Each pose must be a full stack.json')
                frames.append(fp)
            fps=float(obj.get('fps',12))
            if not math.isfinite(fps) or not (1<=fps<=30):raise ValueError('fps must be 1..30')
            result.append({'path':p,'frames':frames,'fps':fps,
                           'position':vec(obj.get('position',[0,0,0]),'position'),
                           'rotation':vec(obj.get('rotation',[0,0,0]),'rotation'),
                           'scale':vec(obj.get('scale',[1,1,1]),'scale',positive=True)})
        return result
    if source.is_dir() and (source/'stack.json').is_file():
        return [{'path':source/'stack.json','position':[0,0,0],'rotation':[0,0,0],'scale':[1,1,1]}]
    if source.is_dir() and (source/'Assets').is_dir() and (source/'ProjectSettings'/'ProjectVersion.txt').is_file():
        if not UNITY_EXPORT.is_file():raise RuntimeError('UnityGLTF exporter not available')
        cmd=[sys.executable,str(UNITY_EXPORT),str(source),'--out',str(outdir/'unitygltf')]
        if unity:cmd.extend(['--unity',unity])
        if all_scenes:cmd.append('--all-scenes')
        subprocess.run(cmd,check=True,timeout=3600)
        glbs=sorted((outdir/'unitygltf'/'glb_scenes').glob('*.glb'))
    elif source.is_file() and source.suffix.lower()=='.glb':
        glbs=[source]
    elif source.is_dir():
        glbs=sorted(p for p in source.rglob('*.glb') if p.is_file() and not p.is_symlink())
    else:raise ValueError('Supported input: original GLB, Unity source, stack.json, stack folder or scene JSON')
    if not glbs or len(glbs)>MAX_UNIQUE:raise ValueError('No GLBs or too many distinct GLBs (>32)')
    converter=GLB_CONVERT
    result=[]
    for index,glb in enumerate(glbs):
        dest=outdir/'stack-assets'/f'{index:03d}-{glb.stem[:42]}'
        cmd=[sys.executable,str(converter),str(glb),'--out',str(dest),'--xy',str(xy),'--z',str(z)]
        if allow_shell:cmd.append('--allow-shell')
        subprocess.run(cmd,check=True,timeout=1800)
        result.append({'path':dest/'stack.json','position':[0,0,0],
                       'rotation':[0,0,0],'scale':[1,1,1]})
    return result


def cache_setup(no_install:bool):
    cache=Path.home()/'.cache'/'meta-original-sprite-stacking'/THREE
    cache.mkdir(parents=True,exist_ok=True)
    cfg={'name':'meta-original-sprite-stacking','private':True,'type':'module',
         'dependencies':{'three':THREE,'esbuild':ESBUILD}}
    config=cache/'package.json'
    if not config.exists() or json.loads(config.read_text())!=cfg:
        config.write_text(json.dumps(cfg,indent=2))
    for name in ('build-stack-html.mjs','stack-runtime.mjs'):
        shutil.copy2(HERE/name,cache/name)
    node=shutil.which('node');npm=shutil.which('npm')
    if not node:raise RuntimeError('Node.js required for offline browser bundle')
    valid=True
    for pkg,version in cfg['dependencies'].items():
        file=cache/'node_modules'/pkg/'package.json'
        if not file.is_file() or json.loads(file.read_text())['version']!=version:
            valid=False
            break
    if not valid:
        if no_install:raise RuntimeError('Pinned Three.js/esbuild not cached; install once with npm')
        if not npm:raise RuntimeError('npm not found')
        subprocess.run([npm,'install','--prefix',str(cache),'--no-audit','--no-fund'],check=True,timeout=400)
    for pkg,version in cfg['dependencies'].items():
        file=cache/'node_modules'/pkg/'package.json'
        if not file.is_file() or json.loads(file.read_text())['version']!=version:
            raise RuntimeError('Pinned Three.js/esbuild version missing after install')
    return node,cache


def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--xy',type=int,default=192)
    p.add_argument('--z',type=int,default=96)
    p.add_argument('--closed-only',action='store_true',help='Strict mode: reject all open meshes instead of preserving thin surface shells')
    p.add_argument('--unity',help='Unity Editor executable for original Unity project')
    p.add_argument('--all-scenes',action='store_true')
    p.add_argument('--no-install',action='store_true')
    args=p.parse_args()
    if not 16<=args.xy<=384 or not 8<=args.z<=192:p.error('Grid limits: xy 16..384, z 8..192')
    source=args.source.expanduser().resolve(strict=True)
    out=args.out.expanduser().resolve()
    html=(out/'sprite-stacking.html') if out.suffix.lower()!='.html' else out
    destination=html.parent
    input_root=source.parent if source.is_file() and source.name=='stack.json' else source
    if source==destination or source==html or input_root==destination or input_root in destination.parents or (source.is_dir() and destination in source.parents):
        raise ValueError('Output and source must be disjoint')
    if html.exists():raise ValueError('Refusing to overwrite existing HTML: '+str(html))
    destination.mkdir(parents=True,exist_ok=True)
    sources=parse_sources(source,destination,args.xy,args.z,not args.closed_only,args.unity,args.all_scenes)
    if len(sources)>MAX_SCENES:raise ValueError('Too many stack instances')
    unique={}; volumes=[]; items=[]; total=0; layers=0
    def register(path):
        nonlocal total,layers
        path=path.resolve(strict=True)
        if path not in unique:
            if len(volumes)>=MAX_UNIQUE:raise ValueError('Too many unique volume textures (32 max)')
            v=volume(path)
            total+=v.pop('raw_bytes')
            if total>MAX_RAW_BYTES:raise ValueError('All stacks together exceed 128 MiB raw RGBA')
            layers+=v.pop('layers')
            unique[path]=len(volumes)
            volumes.append(v)
        return unique[path]
    for entry in sources:
        volume_id=register(entry['path'])
        vol=volumes[volume_id]
        frames=[volume_id]+[register(f) for f in entry.get('frames',[])]
        for frame in frames[1:]:
            candidate=volumes[frame]
            if candidate['dims']!=vol['dims'] or candidate['spacing']!=vol['spacing']:
                raise ValueError('Animated sprite stacking needs exactly aligned full-volume frames')
            if any(abs(a-b)>max(vol['spacing'])*0.001 for a,b in zip(candidate['pivot'],vol['pivot'])):
                raise ValueError('Animated sprite stacking needs unchanged pivot for every pose')
        position=[a+b for a,b in zip(vol['pivot'],entry['position'])]
        items.append({'volume':volume_id,'frames':frames,'fps':entry.get('fps',12),
                      'position':position,'rotation':entry['rotation'],'scale':entry['scale']})
    payload={'name':source.stem if source.is_file() else source.name,
             'volumes':volumes,'items':items,'layerCount':layers,
             'note':'Visual original voxel-slice renderer; no Unity/Godot scripts, physics or AI.'}
    payloadpath=destination/'sprite-stacking-payload.json'
    if payloadpath.exists():raise ValueError('Refusing to overwrite existing build payload')
    payloadpath.write_text(json.dumps(payload,ensure_ascii=True,separators=(',',':')),encoding='utf8')
    node,cache=cache_setup(args.no_install)
    subprocess.run([node,str(cache/'build-stack-html.mjs'),str(payloadpath),str(html)],check=True,timeout=300)
    print('SPRITE_STACK_HTML:',html,'real horizontal slices:',layers,'instances:',len(items))

if __name__=='__main__':
    try:run()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as ex:sys.exit('ERROR: '+str(ex))
