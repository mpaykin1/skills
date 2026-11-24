#!/usr/bin/env python3
"""Verified painted cels -> Blender 4.5+/5.x 2.5D image planes + native GPv3.

Consumes only the already-validated GIF assets ZIP. No generated figure poses, no
limb warping, no fabricated Grease Pencil strokes or made-up .blend binary.
"""
from __future__ import annotations
import argparse
import io
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image


class BlenderBridgeError(ValueError):
    pass


def stop(message):
    raise BlenderBridgeError('Blender Grease Pencil bridge: ' + str(message))


def _name(raw, used):
    if not isinstance(raw,str) or not 1<=len(raw)<=160:stop('invalid actor ID')
    n=re.sub(r'[^A-Za-z0-9_-]+','_',raw).strip('_')
    if not n or n.lower() in used:stop('unsafe or duplicate actor ID: '+raw)
    used.add(n.lower());return n


def _member(path):
    if not isinstance(path,str) or not path or '\\' in path or path.startswith('/') or ':' in path:
        stop('invalid source relative path '+repr(path))
    if any(v in ('','.','..') for v in path.split('/')):stop('path traversal: '+path)
    return path


def _is_num(value):
    return type(value) in (int,float) and math.isfinite(value)


def _png(blob,name,size=None,alpha=False):
    try:
        with Image.open(io.BytesIO(blob)) as f:
            if f.format!='PNG':stop(name+' is not PNG')
            if size and tuple(size)!=f.size:stop(name+' wrong size')
            if alpha:
                a=f.convert('RGBA').getchannel('A').getextrema()
                if a[0]==255 or a[1]==0:stop(name+' needs real alpha silhouette')
            return f.size
    except BlenderBridgeError:raise
    except Exception as exc:stop(name+' unreadable: '+str(exc))


def _strokes(raw, width, height, total_frames):
    if not isinstance(raw,list) or len(raw)>256:stop('blender.gp_strokes must be <=256 hand-authored strokes')
    result=[];used=set()
    for stroke in raw:
        if not isinstance(stroke,dict):stop('invalid GP stroke')
        label=_name(stroke.get('id'),used)
        col=stroke.get('rgba',[0.05,0.04,0.07,1.])
        if not isinstance(col,list) or len(col)!=4 or not all(_is_num(v) and 0<=v<=1 for v in col):
            stop(label+' invalid RGBA ink color')
        size=stroke.get('width_px',2)
        if not _is_num(size) or not .25<=size<=32:stop(label+' invalid stroke width')
        z=stroke.get('z_index',20)
        if not _is_num(z) or not -1000<=z<=1000:stop(label+' invalid ink depth')
        frames=stroke.get('keyframes')
        if not isinstance(frames,list) or not 1<=len(frames)<=256:stop(label+' needs actual hand-drawn ink keyframes')
        normalized=[];prev=0
        for fr in frames:
            if not isinstance(fr,dict) or type(fr.get('frame')) is not int:stop(label+' invalid frame')
            index=fr['frame']
            if not prev<index<=total_frames:stop(label+' stroke frame order/bounds invalid')
            coords=fr.get('points')
            if not isinstance(coords,list) or not 2<=len(coords)<=4096:stop(label+' requires actual >=2 2D ink points')
            for xy in coords:
                if not isinstance(xy,list) or len(xy)!=2 or not all(_is_num(v) for v in xy):
                    stop(label+' invalid pixel-space ink point')
                if not(0<=xy[0]<=width and 0<=xy[1]<=height):stop(label+' ink point outside image')
            normalized.append({'frame':index,'points':coords});prev=index
        result.append({'id':label,'rgba':col,'width_px':float(size),'z_index':float(z),'keyframes':normalized})
    return result


def _config(scene, width, height, fps, total):
    settings=scene.get('blender',{})
    if not isinstance(settings,dict):stop('blender settings must be object')
    ppu=settings.get('pixels_per_unit',100)
    if not _is_num(ppu) or not 16<=ppu<=1000:stop('pixels_per_unit outside 16..1000')
    layers=[]
    raw_layers=settings.get('layers',scene.get('godot',{}).get('layers',[]))
    if not isinstance(raw_layers,list) or len(raw_layers)>64:stop('invalid Blender depth layers')
    for i,layer in enumerate(raw_layers):
        if not isinstance(layer,dict):stop('invalid layer')
        path=_member(layer.get('png'))
        z=layer.get('z_index',0)
        if not _is_num(z) or not -1000<=z<=1000:stop('invalid layer z_index')
        if type(layer.get('visible',True)) is not bool:stop('invalid layer visibility')
        layers.append({'name':re.sub('[^A-Za-z0-9_-]','_',str(layer.get('name',f'Layer{i:02d}'))),
                       'source':path,'z_index':float(z),'visible':layer.get('visible',True)})
    return {'width':width,'height':height,'fps':fps,'frames':total,'pixels_per_unit':float(ppu),
            'layers':layers,'gp_strokes':_strokes(settings.get('gp_strokes',[]),width,height,total)}


def compile_project(verified_zip, output, fps=24, seconds=48, blender_binary=None):
    verified_zip=Path(verified_zip).resolve();output=Path(output).resolve()
    if not verified_zip.is_file():stop('verified pose assets ZIP is missing')
    if type(fps) is not int or type(seconds) is not int or fps<24 or not 40<=seconds<=60 or fps*seconds>1500:
        stop('full character animation requires 40–60s / >=24fps / <=1500 frames')
    project=output/'blender_2_5d_project';project.mkdir(parents=True,exist_ok=True)
    (project/'textures').mkdir(exist_ok=True)
    (project/'sprites').mkdir(exist_ok=True)
    (project/'data').mkdir(exist_ok=True)
    with zipfile.ZipFile(verified_zip) as z:
        if z.testzip() is not None:stop('original ZIP is corrupt')
        try:
            scene=json.loads(z.read('scene.json'))
            gate=json.loads(z.read('motion_gate.json'))
            source=z.read('source.png');background=z.read('background_clean.png')
        except (KeyError,ValueError) as e:stop('required original validation/scene/texture missing: '+str(e))
        if not gate.get('all_actors_pass'):stop('all original characters must pass full-pose motion gate')
        width,height=_png(source,'source.png')
        _png(background,'background_clean.png',(width,height))
        (project/'textures'/'background.png').write_bytes(background)
        spec=_config(scene,width,height,fps,fps*seconds)
        for ix,layer in enumerate(spec['layers']):
            path='project/inputs/'+layer.pop('source')
            try:art=z.read(path)
            except KeyError:stop('authored depth layer missing: '+path)
            _png(art,path,(width,height),alpha=True)
            name=f'textures/plane_{ix:03d}.png'
            (project/name).write_bytes(art);layer['file']=name
        actors=scene.get('actors',[])
        inventory=scene.get('inventory',{}).get('actors',[])
        if not actors or len(actors)!=len(inventory) or set(inventory)!={a.get('id') for a in actors}:
            stop('every visible actor must be in verified inventory')
        processed=[];used=set()
        for actor in actors:
            aid=actor['id'];slug=_name(aid,used)
            rect=actor.get('box')
            if not isinstance(rect,list) or len(rect)!=4 or any(type(v) is not int for v in rect):
                stop(aid+' invalid original pixel box')
            x,y,w,h=rect
            if w<8 or h<8 or x<0 or y<0 or x+w>width or y+h>height:stop(aid+' out-of-bounds box')
            clips=actor.get('clips',[])
            if not isinstance(clips,list) or len(clips)<2:stop(aid+' no multi-action motion')
            idx=0;actions=[]
            for clip in clips:
                frames=clip.get('frames',[]);action=clip.get('action')
                if not isinstance(action,str) or len(frames)<12:stop(aid+' invalid painted action clip')
                for frame in frames:
                    original=_member(frame.get('png'))
                    member='project/inputs/'+original
                    try:art=z.read(member)
                    except KeyError:stop(aid+' missing verified authored cel: '+member)
                    _png(art,member,(w,h),alpha=True)
                    path=project/'sprites'/slug/f'{idx:04d}.png'
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(art)  # exact source bytes, no resampling
                    actions.append(action);idx+=1
            if idx<24 or (fps*seconds)%idx:stop(aid+' cycle does not divide final render length')
            phase=actor.get('phase_frames',0)
            if type(phase) is not int or not 0<=phase<idx:stop(aid+' invalid phase_frames')
            loco=actor.get('locomotion')
            if loco:
                if not isinstance(loco,dict) or not isinstance(loco.get('path'),list) or len(loco['path'])<3:
                    stop(aid+' invalid world-space locomotion path')
                if loco['path'][0].get('frame')!=0 or loco['path'][-1].get('frame')!=idx:
                    stop(aid+' locomotion path not closed over own cel cycle')
            processed.append({'id':aid,'slug':slug,'box':rect,'z_index':int(actor.get('z',0)),
                              'frame_count':idx,'phase_frames':phase,'locomotion':loco,
                              'actions':actions})
        spec['actors']=processed
        (project/'data'/'scene.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),'utf8')
        (project/'data'/'source_scene.json').write_text(json.dumps(scene,ensure_ascii=False,indent=2),'utf8')
    # Save a real executable Blender Python project source even when Blender
    # binary is not installed. A .blend file is created only by actual Blender.
    script=Path(__file__).with_name('blender_build_scene.py')
    if not script.is_file():stop('bundled native Blender builder missing')
    shutil.copy2(script,project/'build_blender.py')
    actual=False
    if blender_binary:
        raw=str(blender_binary)
        binary=shutil.which(raw) or (str(Path(raw).expanduser().resolve()) if Path(raw).expanduser().is_file() else None)
        if not binary:stop('requested Blender executable missing; no .blend manufactured')
        try:
            proc=subprocess.run([binary,'--background','--factory-startup','--python-exit-code','3',
                    '--python',str(project/'build_blender.py'),'--',str(project)],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=240,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:stop('native Blender launch failed: '+str(exc))
        if proc.returncode or not (project/'living_scene.blend').is_file():
            stop('native Blender scene build failed: '+(proc.stderr+'\n'+proc.stdout)[-2500:])
        actual=True
    (project/'README.txt').write_text('Living Image Animator: original painted RGBA cels and editable 2.5D Blender Grease Pencil scene.\n'
       'If Blender was not installed during export, open Blender 4.5 LTS/5.x and run build_blender.py with project folder as argument.\n'
       'All visible character frames are original artwork; Grease Pencil ink requires authored source points.\n','utf8')
    package=output/'living_scene_blender.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
        for file in sorted(project.rglob('*')):
            if file.is_file():dst.write(file,'living_scene_blender/'+file.relative_to(project).as_posix())
    with zipfile.ZipFile(package) as pkg:
        if pkg.testzip() is not None or 'living_scene_blender/build_blender.py' not in pkg.namelist():
            stop('new Blender project archive is corrupt')
        if actual and 'living_scene_blender/living_scene.blend' not in pkg.namelist():
            stop('native .blend missing after Blender ran')
    return package,{'blender_native_executed':actual,'blender_scene_file':actual,
                    'blender_actors':len(processed),'blender_layers':len(spec['layers']),
                    'blender_gp_strokes':len(spec['gp_strokes'])}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--verified-zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--fps',type=int,default=24)
    ap.add_argument('--seconds',type=int,default=48)
    ap.add_argument('--blender',help='Real Blender 4.5+ binary, required to create actual .blend')
    a=ap.parse_args()
    result,summary=compile_project(a.verified_zip,a.out,a.fps,a.seconds,a.blender)
    print(json.dumps({'package':str(result),**summary},ensure_ascii=False))

if __name__=='__main__':main()
