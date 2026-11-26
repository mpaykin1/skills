#!/usr/bin/env python3
"""Unified delivery wrapper with actual ComfyUI ControlNet Aux pose-guide ingestion.

Never replaces, bypasses or weakens Krita/OpenToonz/Pixelorama/MMPose/DLC and
full-cel motion tests. Adds verified optional pose references to ZIP.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from controlnet_aux_bridge import compile_reference,PoseAuxError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    p.add_argument('--pixelorama')
    p.add_argument('--opentoonz')
    p.add_argument('--mmpose-device')
    p.add_argument('--comfyui-url')
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    scene=a.scene.resolve();out=a.out.resolve()
    cfg=json.loads(scene.read_text('utf8'))
    sources=[];guide_files=[];metrics={}
    for actor in cfg.get('actors',[]):
        config=actor.get('controlnet_aux_pose')
        if config is None:continue
        if not isinstance(config,dict):raise PoseAuxError('controlnet_aux_pose must be an object')
        ident=actor['id']
        if not ident.replace('-','').replace('_','').isalnum():
            raise PoseAuxError('Actor ID contains characters unsafe for guide path')
        guide,src,metric=compile_reference(scene,actor,config,
            out/'controlnet_aux_references'/(ident+'.json'),a.comfyui_url)
        guide_files.append(guide)
        if src:sources.append(src)
        metrics[ident]=metric
    args=[sys.executable,str(Path(__file__).with_name('unified_delivery.py')),
          str(a.source.resolve()),'--scene',str(scene),'--out',str(out),
          '--seconds',str(a.seconds),'--fps',str(a.fps),'--max-width',str(a.max_width)]
    for key,option in [('pixelorama',a.pixelorama),('opentoonz',a.opentoonz),('mmpose-device',a.mmpose_device)]:
        if option:args.extend(['--'+key,option])
    if a.preflight_only:args.append('--preflight-only')
    proc=subprocess.run(args,check=False)
    if proc.returncode:raise SystemExit(proc.returncode)
    if a.preflight_only:return
    zip_path=out/'living_scene_assets.zip';gif=out/'living_scene.gif'
    if not gif.is_file() or not zip_path.is_file():
        raise PoseAuxError('No verified renderer GIF/ZIP; output blocked')
    with zipfile.ZipFile(zip_path,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        entries=set(z.namelist())
        for f in guide_files:
            item='project/controlnet_aux/'+f.name
            if item in entries:raise PoseAuxError('Duplicate guide member')
            z.write(f,item);entries.add(item)
        for i,f in enumerate(sources):
            item='project/controlnet_aux/source_'+str(i)+'_'+f.name
            if item in entries:raise PoseAuxError('Duplicate pose source member')
            z.write(f,item);entries.add(item)
        z.writestr('controlnet_aux_reference_metrics.json',json.dumps(metrics,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip():raise PoseAuxError('Corrupted pose ZIP')
    print(json.dumps({'gif':str(gif),'zip':str(zip_path),'controlnet_aux_references':len(guide_files),
                      'pose_generation':'NOT PERFORMED: author genuine cels in Krita/OpenToonz/Pixelorama'},ensure_ascii=False))

if __name__=='__main__':main()
