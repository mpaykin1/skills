#!/usr/bin/env python3
"""Scene-level sprite stacking entrypoint that preserves independently movable parts.

Original static GLB or a folder/UnityGLTF export: scene per node -> actual
RGBA layer volumes -> one visual-only HTML per original scene. For already
approved stack.json/scene.json, defer to the established stack_to_html.py.
Original native Godot/Unity Web remains the only full playable game route.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
from stack_scene_parts import build as build_parts

HERE=Path(__file__).resolve().parent
UNITY_EXPORT=HERE.parent.parent/'godot-game-to-html'/'scripts'/'export_unity_glb.py'


def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--xy',type=int,default=128)
    p.add_argument('--z',type=int,default=64)
    p.add_argument('--unity',help='Trusted original Unity Editor executable')
    p.add_argument('--all-scenes',action='store_true')
    p.add_argument('--closed-only',action='store_true')
    p.add_argument('--assets-only',action='store_true')
    p.add_argument('--no-install',action='store_true')
    p.add_argument('--manifold',choices=['off','audit','normalize'],default='audit')
    a=p.parse_args()
    src=a.source.expanduser().resolve(strict=True)
    out=a.out.expanduser().resolve()
    if (src.is_dir() and (src==out or src in out.parents or out in src.parents)) or (src.is_file() and (src==out or out==src.parent or out in src.parents)):
        raise ValueError('Original data and derivative output directory must not overlap')
    if src.is_file() and src.suffix.lower()=='.json':
        if a.assets_only:raise ValueError('Already-authored PNG stacks need no new slice extraction')
        out.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,str(HERE/'stack_to_html.py'),str(src),'--out',str(out/'sprite-stacking.html')]
        if a.no_install:cmd.append('--no-install')
        subprocess.run(cmd,check=True)
        return
    if src.is_dir() and (src/'Assets').is_dir() and (src/'ProjectSettings'/'ProjectVersion.txt').is_file():
        # Unity source -> actual authored scene GLBs via the previously installed UnityGLTF.
        cmd=[sys.executable,str(UNITY_EXPORT),str(src),'--out',str(out/'unitygltf')]
        if a.unity:cmd+=['--unity',a.unity]
        if a.all_scenes:cmd.append('--all-scenes')
        subprocess.run(cmd,check=True,timeout=3600)
        glbs=sorted((out/'unitygltf'/'glb_scenes').glob('*.glb'))
    elif src.is_file() and src.suffix.lower()=='.glb':
        glbs=[src]
    elif src.is_dir():
        if (src/'stack.json').is_file():
            if a.assets_only:raise ValueError('No extraction needed for approved existing stack slices')
            out.mkdir(parents=True,exist_ok=True)
            cmd=[sys.executable,str(HERE/'stack_to_html.py'),str(src/'stack.json'),
                 '--out',str(out/'sprite-stacking.html')]
            if a.no_install:cmd.append('--no-install')
            subprocess.run(cmd,check=True)
            return
        glbs=sorted(f for f in src.rglob('*.glb') if f.is_file() and not f.is_symlink())
    else:
        raise ValueError('Supply original GLB, Unity source, or approved stack.json/scene.json')
    if not glbs or len(glbs)>32:
        raise ValueError('No source GLB scenes, or more than 32 scenes. Split into authored regions.')
    if src.is_file() and src.suffix.lower()=='.glb':
        build_parts(src,out,a.xy,a.z,not a.closed_only,not a.assets_only,a.no_install,a.manifold)
    else:
        for index,glb in enumerate(glbs):
            area=out/'areas'/f'{index:03d}-{glb.stem[:40]}'
            build_parts(glb,area,a.xy,a.z,not a.closed_only,not a.assets_only,a.no_install,a.manifold)
    print('Original game resources unchanged; visual output is not full gameplay')


if __name__=='__main__':
    try:run()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:
        sys.exit('ERROR: '+str(e))
