#!/usr/bin/env python3
"""Complete CPU Sprite Stacking asset from GLB/OBJ or Blender MONSTER_RIG.

Bake all real rig actions by default; output true XYZ volumetric atlases, orbit
GIFs, unchanged source, and one runtime-readable library.json for Three.js.
"""
from __future__ import annotations
import argparse
import json
import hashlib
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
    p.add_argument('--hybrid-glb',help='Approved matching, animated original GLB for hidden shadow rig and real 3D attachments')
    p.add_argument('--no-hybrid',action='store_true',help='Do not bundle GLB shadow rig (legacy stack-only mode)')
    p.add_argument('--attachment-prefix',default='HYBRID_3D_',help='Only these authored GLB objects are visible real 3D attachments')
    p.add_argument('--roughness',type=float,default=0.76,help='CPU-baked surface roughness for the monster volume')
    p.add_argument('--no-surface-maps',action='store_true',help='Legacy diffuse-only stack output')
    args=p.parse_args(argv)
    if not 0.05<=args.roughness<=1:p.error('roughness must be 0.05..1.0')
    if '/' in args.attachment_prefix or '\\' in args.attachment_prefix:p.error('attachment-prefix must be a short GLB node prefix')
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
        if args.input_blend:
            cmd+=['--shared-grid',str(out/'shared_grid.json'),
                  '--pose-timing',str(poses/'poses.json')]
        if args.no_surface_maps:cmd+=['--no-surface-maps']
        cmd+=['--roughness',str(args.roughness)]
        if args.allow_open:cmd.append('--allow-open')
        subprocess.run(cmd,check=True)
        library[name]=f'stack/{name}/clip.json'
    preferred='IDLE_BREATH' if 'IDLE_BREATH' in library else next(iter(library))
    manifest={'format':'monster-sprite-stack-library-v2','defaultClip':preferred,
              'clips':library,'renderer':'runtime/sprite_stack_three.js',
              'source_mode':'baked Blender poses' if args.input_blend else 'static original 3D source',
              'fps':args.fps}
    # Bundle source-author-approved GLB unchanged, never hide a mere generic proxy.
    source_glb=Path(args.hybrid_glb).expanduser().resolve() if args.hybrid_glb else (
        Path(args.input_glb).expanduser().resolve() if args.input_glb and
        Path(args.input_glb).suffix.lower()=='.glb' else None)
    if args.no_hybrid:source_glb=None
    if args.hybrid_glb and not source_glb.is_file():raise FileNotFoundError('Original animated rig GLB missing')
    if source_glb is not None:
        if source_glb.suffix.lower()!='.glb' or not source_glb.is_file():
            raise ValueError('Hybrid GLB must be an existing original .glb asset')
        bundled=out/'hybrid'/'original_rig.glb';bundled.parent.mkdir()
        shutil.copyfile(source_glb,bundled)
        source_hash=hashlib.sha256(bundled.read_bytes()).hexdigest()
        manifest['hybrid']={'format':'monster-hybrid-v1','rigGlb':'hybrid/original_rig.glb',
            'attachmentPrefix':args.attachment_prefix,'colliderPrefix':'COLLIDER_',
            'renderer':'runtime/hybrid_monster_three.js',
            'shadow':'invisible, animated original 3D body (requires Three.js shadow map)',
            'source_sha256':source_hash,'worldUp':'Y','preserveSource':True}
    # Copy complete runtime scripts next to the asset for direct local import.
    renderdir=out/'runtime';renderdir.mkdir()
    for js in ('sprite_stack_three.js','hybrid_monster_three.js'):
        shutil.copyfile(SCRIPTS.parent/'runtime'/js,renderdir/js)
    (out/'library.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('[sprite stacking] PRIMARY asset:',out/'library.json')
    print('[sprite stacking] REAL 3D orbit:',stacks/preferred/'preview/orbit_360.gif')

if __name__=='__main__':main()
