#!/usr/bin/env python3
"""Run official Instant Meshes on a Blender monster without losing its rig.

Needs Blender 4.2+, a built official Instant Meshes CLI, and the current
Monster Anatomy 3D scripts. In absence of either dependency, aborts rather
than substituting decimation or claiming successful integration.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

SCRIPTS=Path(__file__).resolve().parent

def run(cmd, timeout=1800):
    print('+',' '.join(str(x) for x in cmd),flush=True)
    subprocess.run([str(x) for x in cmd],check=True,timeout=timeout)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--blender',default='blender')
    ap.add_argument('--instant-bin',required=True)
    ap.add_argument('--blend',required=True)
    ap.add_argument('--output-blend',required=True)
    ap.add_argument('--output-glb',required=True)
    ap.add_argument('--work-dir',default='')
    ap.add_argument('--ratio',type=float,default=.4)
    ap.add_argument('--min-faces',type=int,default=220)
    ap.add_argument('--crease',type=float,default=48)
    ap.add_argument('--max-dist-relative',type=float,default=.04)
    ap.add_argument('--mean-dist-relative',type=float,default=.012)
    opt=ap.parse_args()
    if not .10<=opt.ratio<=.80:ap.error('ratio must be 0.10..0.80')
    if opt.min_faces<90:ap.error('min-faces must be at least 90')
    if not 1<=opt.crease<=180:ap.error('crease angle must be 1..180')
    candidate=Path(opt.instant_bin).expanduser().resolve()
    if not candidate.is_file():
        other=shutil.which(opt.instant_bin)
        if other:candidate=Path(other).resolve()
        else:ap.error('Missing Instant Meshes CLI binary: '+opt.instant_bin)
    blender=opt.blender
    if not Path(opt.blend).is_file():ap.error('Missing Blender scene: '+opt.blend)
    work=Path(opt.work_dir).resolve() if opt.work_dir else Path(opt.output_blend).resolve().parent/'instant-retopo-work'
    work.mkdir(parents=True,exist_ok=True)
    common=['--work-dir',work,'--ratio',opt.ratio,'--min-faces',opt.min_faces,
            '--max-dist-relative',opt.max_dist_relative,'--mean-dist-relative',opt.mean_dist_relative]
    run([blender,'--background','--python',SCRIPTS/'instant_blender_bridge.py','--',
         '--phase','prepare','--blend',opt.blend,*common])
    manifest_path=work/'manifest.json'
    if not manifest_path.is_file():raise RuntimeError('Blender did not create retopology manifest')
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    for item in manifest['items']:
        src=work/(item['stem']+'_source.obj');dst=work/(item['stem']+'_retopo.obj')
        # Respect intended output target, request quad layout; avoid GUI mode.
        run([candidate,'--deterministic','--rosy','4','--posy','4','--faces',item['target_faces'],
             '--crease',opt.crease,'--output',dst,src],timeout=1200)
        if not dst.is_file() or dst.stat().st_size<100:
            raise RuntimeError('Instant Meshes failed to produce '+str(dst))
    run([blender,'--background','--python',SCRIPTS/'instant_blender_bridge.py','--',
         '--phase','finish','--blend',opt.blend,'--output-blend',opt.output_blend,
         '--output-glb',opt.output_glb,*common])
    print('Finished with official quad remesher + deform/UV transfer: '+str(Path(opt.output_glb).resolve()))

if __name__=='__main__':main()
