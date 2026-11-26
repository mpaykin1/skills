#!/usr/bin/env python3
"""One command: Open Mocap CPU video -> same rig + baked muscle morphs + GLB."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def call(parts):
    subprocess.run([str(x) for x in parts],check=True)


def main(argv=None):
    p=argparse.ArgumentParser(description='CPU-only Open Mocap -> Monster Anatomy 3D animated GLB')
    p.add_argument('--blender',default='blender')
    p.add_argument('--blend',type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--video',type=Path)
    group.add_argument('--landmarks',type=Path)
    p.add_argument('--side-video',type=Path)
    p.add_argument('--output-blend',type=Path,required=True)
    p.add_argument('--output-glb',type=Path,required=True)
    p.add_argument('--clip',default='MOCAP_WALK')
    p.add_argument('--bone-map',type=Path)
    p.add_argument('--mirror',action='store_true')
    a=p.parse_args(argv)
    exe=shutil.which(a.blender) if '/' not in a.blender and '\\' not in a.blender else str(Path(a.blender).expanduser().resolve())
    if not exe or not Path(exe).is_file():p.error('Blender executable not found. Install Blender 4.5+ (CPU mode).')
    src=a.blend.expanduser().resolve()
    if not src.is_file() or src.suffix.lower()!='.blend':p.error('Input must be existing .blend with MONSTER_RIG')
    out=a.output_blend.expanduser().resolve(); glb=a.output_glb.expanduser().resolve()
    if out.exists() or glb.exists() or len({src,out,glb})!=3:p.error('Outputs must be separate, nonexisting files')
    if a.side_video and not a.video:p.error('--side-video requires --video')
    if a.video:
        if not a.video.is_file():p.error('CPU mocap video not found')
        coords=out.parent/(out.stem+'_open_mocap_landmarks.json')
        if coords.exists():p.error('Intermediate landmarks output exists, refusing overwrite')
        cmd=[sys.executable,HERE/'open_mocap_cpu_capture.py','--video',a.video,'--output',coords]
        if a.side_video:cmd+=['--side-video',a.side_video]
        call(cmd)
    else:
        coords=a.landmarks.expanduser().resolve()
        if not coords.is_file():p.error('Supplied Open Mocap motion landmarks JSON missing')
    cmd=[exe,'--background','--factory-startup','--python-exit-code','3',
        '--python',HERE/'open_mocap_retarget_blender.py','--',
        '--blend',src,'--landmarks',coords,'--output-blend',out,'--output-glb',glb,
        '--clip',a.clip]
    if a.bone_map:cmd+=['--bone-map',a.bone_map]
    if a.mirror:cmd+=['--mirror']
    call(cmd)
    print('CPU motion:',out,glb)

if __name__=='__main__':main()
