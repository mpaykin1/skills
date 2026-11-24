#!/usr/bin/env python3
"""Complete CPU Sprite Stacking asset from GLB/OBJ or Blender MONSTER_RIG.

Bake all real rig actions by default; output true XYZ volumetric atlases, orbit
GIFs, unchanged source, and one runtime-readable library.json for Three.js.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

SCRIPTS=Path(__file__).resolve().parent


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    src=p.add_mutually_exclusive_group(required=True)
    src.add_argument('--input-glb',help='Existing real .glb/.obj/.ply mesh')
    src.add_argument('--input-blend',help='Existing animated Blender MONSTER_RIG')
    p.add_argument('--blender',default='blender')
    p.add_argument('--clip',default='ALL',help='ALL (default) or one existing action')
    p.add_argument('--frames',type=int,default=12)
    p.add_argument('--fps',type=int,default=12)
    p.add_argument('--xy-size',type=int,choices=(64,96,128,192,256),default=96)
    p.add_argument('--z-slices',type=int,choices=(32,48,64,96,128),default=64)
    p.add_argument('--output',default='build/monster-sprite-stacking')
    p.add_argument('--allow-open',action='store_true')
    args=p.parse_args(argv)
    out=Path(args.output).expanduser().resolve()
    if out.exists():p.error('Output already exists; never overwrite source-approved stacks')
    out.mkdir(parents=True)
    clips={}
    if args.input_blend:
        blender=shutil.which(args.blender) if '/' not in args.blender and '\\' not in args.blender else args.blender
        if not blender or not Path(blender).is_file():p.error('Blender 4.5+ required to bake original MONSTER_RIG poses')
        poses=out/'pose_source_objs'
        subprocess.run([blender,'--background','--factory-startup','--python-exit-code','3',
                        '--python',str(SCRIPTS/'export_sprite_poses_blender.py'),'--',
                        '--blend',args.input_blend,'--output',str(poses),'--clip',args.clip,
                        '--frames',str(args.frames)],check=True)
        metadata=json.loads((poses/'poses.json').read_text(encoding='utf8'))
        clips={name:['--frames-dir',str(poses/name)] for name in metadata['clips']}
        # The SAME pivot and XYZ grid must span ALL action poses, not just each
        # separate animation clip; otherwise clip switches visibly jump.
        from sprite_stack_cpu import compute_grid, load_geometry
        every=[]
        for name in clips:
            for source in sorted((poses/name).glob('*.obj')):
                every.append(load_geometry(source))
        dims,spacing,pivot=compute_grid(every,args.xy_size,args.z_slices)
        gridfile=out/'shared_grid.json'
        gridfile.write_text(json.dumps({'dimensions':dims,'spacing':spacing,'pivot':pivot},indent=2),encoding='utf8')
    else:
        clips={'STATIC':['--input',args.input_glb]}
    stacks=out/'stack';stacks.mkdir()
    library={}
    for name,mode in clips.items():
        dest=stacks/name
        cmd=[sys.executable,str(SCRIPTS/'sprite_stack_cpu.py'),*mode,'--output',str(dest),
             '--xy-size',str(args.xy_size),'--z-slices',str(args.z_slices),
             '--fps',str(args.fps),'--clip',name,'--orbit-gif']
        if args.input_blend:cmd+=['--shared-grid',str(out/'shared_grid.json')]
        if args.allow_open:cmd.append('--allow-open')
        subprocess.run(cmd,check=True)
        library[name]=f'stack/{name}/clip.json'
    preferred='IDLE_BREATH' if 'IDLE_BREATH' in library else next(iter(library))
    manifest={'format':'monster-sprite-stack-library-v2','defaultClip':preferred,
              'clips':library,'renderer':'runtime/sprite_stack_three.js',
              'source_mode':'baked Blender poses' if args.input_blend else 'static original 3D source',
              'fps':args.fps}
    (out/'library.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('[sprite stacking] PRIMARY asset:',out/'library.json')
    print('[sprite stacking] REAL 3D orbit:',stacks/preferred/'preview/orbit_360.gif')

if __name__=='__main__':main()
