#!/usr/bin/env python3
"""Opt-in Manifold3D preprocessing for original static GLB sprite stacking.

Works with separate authored static scene-node stacks (default), or explicitly
unions a single set of closed static meshes. Native WebGL remains full gameplay.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
STACK=HERE.parent.parent/'sprite-stacking-priority'/'scripts'

def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('glb',type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--manifold',choices=('audit','normalize','union','off'),default='audit')
    p.add_argument('--voxelizer',choices=('auto','open3d','trimesh'),default='auto')
    p.add_argument('--xy',type=int,default=128)
    p.add_argument('--z',type=int,default=64)
    p.add_argument('--assets-only',action='store_true')
    p.add_argument('--no-install',action='store_true')
    args=p.parse_args()
    src=args.glb.expanduser().resolve(strict=True)
    out=args.out.expanduser().resolve()
    if src.suffix.lower()!='.glb':p.error('Only original static .glb is accepted')
    if out==src.parent or out in src.parents or src in out.parents:
        p.error('Derivative must be outside the original GLB directory')
    if out.exists() and any(out.iterdir()):p.error('Output must be empty')
    if args.manifold=='union':
        cmd=[sys.executable,str(STACK/'stack_from_glb.py'),str(src),
             '--out',str(out/'static-union-stack'),'--xy',str(args.xy),'--z',str(args.z),
             '--voxelizer',args.voxelizer,'--manifold','union']
        subprocess.run(cmd,check=True)
        if not args.assets_only:
            cmd=[sys.executable,str(STACK/'stack_to_html.py'),str(out/'static-union-stack'/'stack.json'),
                 '--out',str(out/'sprite-stacking.html')]
            if args.no_install:cmd.append('--no-install')
            subprocess.run(cmd,check=True)
    else:
        cmd=[sys.executable,str(STACK/'stack_scene_to_html.py'),str(src),
             '--out',str(out),'--xy',str(args.xy),'--z',str(args.z),
             '--manifold',args.manifold]
        if args.no_install:cmd.append('--no-install')
        if args.assets_only:cmd.append('--assets-only')
        subprocess.run(cmd,check=True)
    print('Original GLB unchanged; derivative sprite stack generated; this is not native gameplay')

if __name__=='__main__':
    try:run()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:
        sys.exit('ERROR: '+str(e))
