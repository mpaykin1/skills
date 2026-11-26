#!/usr/bin/env python3
"""Conservative source asset optimizer for a COPIED Godot tree.

Tools are optional external open-source executables. Never alters source project
unless explicitly supplied a copied working tree with --apply. Optimize in a
temporary file, only retain candidates that are smaller and parse successfully.

Lossless defaults: oxipng PNG recompression. glTF dedup/prune is opt-in because
reimport/animation/scene graph can change and must be visually inspected.
Lossy modes (gltfpack, FFmpeg Vorbis) are opt-in and never enabled by default.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

IGNORED={'.git','.godot','build','dist','release','node_modules'}

def available(binary):
    return shutil.which(binary) or (str(Path(binary).resolve()) if Path(binary).is_file() else None)

def candidate(cmd, source:Path, target:Path, *, timeout=120):
    if not cmd or not available(cmd[0]): return False
    run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       timeout=timeout,check=False)
    if run.returncode!=0: return False
    if not target.exists() or target.stat().st_size < 32: return False
    if target.stat().st_size >= source.stat().st_size: return False
    return True

def verify_glb(path:Path):
    with path.open('rb') as f:
        head=f.read(12)
    return (len(head)==12 and head[:4]==b'glTF' and
            int.from_bytes(head[4:8],'little')==2 and
            int.from_bytes(head[8:12],'little')==path.stat().st_size)

def optimize_png(src:Path):
    with tempfile.TemporaryDirectory() as t:
        out=Path(t)/src.name
        shutil.copy2(src,out)
        # oxipng writes in-place; lossless without --strip to retain metadata
        tool=available('oxipng')
        if not tool:return 0
        p=subprocess.run([tool,'-o','2','--',str(out)],capture_output=True,timeout=120)
        if p.returncode==0 and out.stat().st_size<src.stat().st_size:
            before=src.stat().st_size
            os.replace(out,src)
            return before-src.stat().st_size
    return 0

def optimize_glb(src:Path, mode:str):
    if mode=='none':return 0
    with tempfile.TemporaryDirectory() as t:
        dst=Path(t)/src.name
        if mode=='dedup':
            tool=available('gltf-transform')
            if not tool:return 0
            step=Path(t)/'dedup.glb'
            cmds=[[tool,'dedup',str(src),str(step)],
                  [tool,'prune',str(step),str(dst)]]
            for command in cmds:
                r=subprocess.run(command,capture_output=True,timeout=180)
                if r.returncode!=0:return 0
        elif mode=='gltfpack':
            tool=available('gltfpack')
            if not tool:return 0
            # No -cc/-tc: Godot GLB importer may not support meshopt/KTX2 ext.
            r=subprocess.run([tool,'-i',str(src),'-o',str(dst)],capture_output=True,timeout=180)
            if r.returncode!=0:return 0
        if not dst.exists() or not verify_glb(dst) or dst.stat().st_size>=src.stat().st_size:return 0
        before=src.stat().st_size
        os.replace(dst,src)
        return before-src.stat().st_size
    return 0

def optimize_ogg(src:Path, quality:int):
    tool=available('ffmpeg')
    if not tool:return 0
    with tempfile.TemporaryDirectory() as t:
        dst=Path(t)/src.name
        r=subprocess.run([tool,'-hide_banner','-loglevel','error','-y','-i',str(src),
          '-map','0:a:0','-c:a','libvorbis','-q:a',str(quality),str(dst)],capture_output=True,timeout=120)
        if r.returncode!=0 or not dst.exists() or dst.stat().st_size>=src.stat().st_size:return 0
        before=src.stat().st_size
        os.replace(dst,src)
        return before-src.stat().st_size

def main():
    ap=argparse.ArgumentParser(description='Conservative lossless/opt-in assets optimization on COPIED Godot source')
    ap.add_argument('project',type=Path)
    ap.add_argument('--apply',action='store_true',help='Modify this folder (NEVER original: use copied build tree)')
    ap.add_argument('--glb',choices=['none','dedup','gltfpack'],default='none')
    ap.add_argument('--ogg-quality',type=int,default=None,help='Opt-in lossy Vorbis re-encode (0..10)')
    a=ap.parse_args()
    project=a.project.resolve(strict=True)
    if not (project/'project.godot').is_file():raise ValueError('Expected a Godot project; use a separate copy')
    if a.ogg_quality is not None and not 0<=a.ogg_quality<=10:raise ValueError('Vorbis quality must be 0..10')
    counts={'png':0,'glb':0,'ogg':0,'saved':0}
    for src in project.rglob('*'):
        if not src.is_file() or any(p in IGNORED for p in src.relative_to(project).parts):continue
        suffix=src.suffix.lower()
        if suffix not in ('.png','.glb','.ogg'):continue
        if not a.apply:continue
        before=src.stat().st_size
        try:
            if suffix=='.png': saving=optimize_png(src)
            elif suffix=='.glb': saving=optimize_glb(src,a.glb)
            else:saving=optimize_ogg(src,a.ogg_quality) if a.ogg_quality is not None else 0
        except (OSError, subprocess.TimeoutExpired):saving=0
        if saving:
            counts[suffix[1:]]+=1
            counts['saved']+=saving
        if src.stat().st_size > before:raise RuntimeError('Regression: asset grew')
    print('Optimized copied project assets:',counts,'mode=',a.glb,'lossy_ogg=',a.ogg_quality is not None)
    if not a.apply: print('Dry-run: pass --apply ONLY for a copied Godot project; source is unchanged')

if __name__=='__main__':main()
