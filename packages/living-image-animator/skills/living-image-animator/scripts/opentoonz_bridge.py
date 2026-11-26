#!/usr/bin/env python3
"""OpenToonz .tnz -> verifiable, original full-pose RGBA PNG frames.

Export uses the real tcomposer binary (not a mock or a .tnz parser); downstream
pose_sequence_delivery.py enforces all-actor silhouette, amplitude and continuity.
No rotating still artwork, synthetic joints, made-up frames or opaque cels.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from PIL import Image

class OpenToonzError(ValueError):
    pass


def resolve_inside(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise OpenToonzError('Source path must be relative to scene.json: '+repr(raw))
    base=root.resolve(); dest=(base/raw).resolve()
    if dest!=base and base not in dest.parents:
        raise OpenToonzError('Source path escapes scene directory: '+raw)
    if not dest.is_file():
        raise OpenToonzError('Missing OpenToonz source/asset: '+str(dest))
    return dest


def resolve_tcomposer(explicit=None) -> str:
    raw=explicit or os.environ.get('OPENTOONZ_TCOMPOSER')
    if raw:
        resolved=shutil.which(raw)
        if not resolved:
            p=Path(raw).expanduser()
            resolved=str(p.resolve()) if p.is_file() else None
    else:
        resolved=next((shutil.which(name) for name in ('tcomposer','tcomposer.exe') if shutil.which(name)), None)
    if not resolved:
        raise OpenToonzError('OpenToonz tcomposer executable missing; supply --opentoonz /path/to/tcomposer or OPENTOONZ_TCOMPOSER')
    return str(Path(resolved).resolve())


def load_landmarks(jsonfile: Path, count: int, box) -> list[dict]:
    data=json.loads(jsonfile.read_text('utf8'))
    rows=data.get('frames') if isinstance(data,dict) else data
    if not isinstance(rows,list) or len(rows)!=count:
        raise OpenToonzError(f'{jsonfile.name}: expected {count} manually annotated joint maps, got {len(rows) if isinstance(rows,list) else None}')
    w,h=map(int,box[2:])
    first_keys=None
    for n,row in enumerate(rows):
        if not isinstance(row,dict) or 'root' not in row or len(row)<3:
            raise OpenToonzError(f'{jsonfile.name} frame {n}: root + >=2 visible anatomical landmarks required')
        keys=set(row)
        if first_keys is None:first_keys=keys
        if keys!=first_keys:
            raise OpenToonzError(f'{jsonfile.name} frame {n}: joint labels change between poses')
        for name,pos in row.items():
            if not isinstance(pos,list) or len(pos)!=2 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in pos):
                raise OpenToonzError(f'{jsonfile.name} frame {n}: malformed joint {name}')
            if not (0<=pos[0]<w and 0<=pos[1]<h):
                raise OpenToonzError(f'{jsonfile.name} frame {n}: joint {name} outside {w}x{h} sprite')
    return rows


def _sort_frames(out_dir:Path, count:int, start:int) -> list[Path]:
    found=sorted(out_dir.glob('frames*.png'))
    if len(found)!=count:
        raise OpenToonzError(f'tcomposer exported {len(found)} PNGs instead of {count}; render range must match author annotations')
    ids=[]
    for f in found:
        m=re.fullmatch(r'frames\.(\d+)\.png',f.name,re.I)
        if not m:
            raise OpenToonzError('Unexpected OpenToonz filename: '+f.name)
        ids.append((int(m.group(1)),f))
    ids.sort(key=lambda x:x[0])
    actual=[i for i,_ in ids]; expected=list(range(start,start+count))
    if actual!=expected:
        raise OpenToonzError(f'OpenToonz frame IDs mismatch: expected {expected[0]}..{expected[-1]}, got {actual[:2]}...{actual[-2:]}')
    return [p for _,p in ids]


def render_tnz(binary:str, project:Path, out_dir:Path, start:int, count:int, box:list, joint_maps:list) -> list[tuple[Path,dict]]:
    out_dir.mkdir(parents=True,exist_ok=True)
    # Disallow stale data: only files produced by this invocation count as a render.
    for f in out_dir.glob('frames*.png'): f.unlink()
    output=out_dir/'frames..png'
    cmd=[binary,str(project),'-o',str(output),'-range',str(start),str(start+count-1),'-step','1']
    try:
        proc=subprocess.run(cmd,cwd=project.parent,capture_output=True,text=True,timeout=240,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise OpenToonzError('tcomposer unavailable/failed to start: '+str(e)) from e
    if proc.returncode!=0:
        raise OpenToonzError(f'tcomposer exited {proc.returncode}: '+(proc.stderr or proc.stdout)[-1800:])
    pngs=_sort_frames(out_dir,count,start)
    w,h=map(int,box[2:]);result=[]
    for i,f in enumerate(pngs):
        with Image.open(f) as im:
            # Never silently discard alpha from an opaque OpenToonz output.
            if im.mode not in ('RGBA','LA','P'):
                raise OpenToonzError(f'{f.name}: missing alpha; configure transparent OpenToonz camera BG and RGBA PNG')
            rgba=im.convert('RGBA')
            if rgba.size!=(w,h):
                raise OpenToonzError(f'{f.name}: expected {w}x{h} registered pose, found {rgba.size}')
            alpha=rgba.getchannel('A')
            if not alpha.getbbox():
                raise OpenToonzError(f'{f.name}: empty frame, missing character drawing')
            lo,hi=alpha.getextrema()
            if lo==255:
                raise OpenToonzError(f'{f.name}: fully opaque frame; background removal is forbidden')
            # Save exact RGBA pixels from the independent OpenToonz render, no warp.
            rgba.save(f)
            result.append((f,joint_maps[i]))
    return result


def compile_scene(scene_file:Path, out_dir:Path, binary=None):
    """Compile OpenToonz clips, copying other Pixelorama/PNG input paths intact.

    Returns (scene_path, source_files_for_zip). Output is an intermediate scene
    accepted unchanged by pixelorama_bridge.compile_scene and pose gate.
    """
    scene_file=Path(scene_file).resolve();root=scene_file.parent
    original=json.loads(scene_file.read_text('utf8'))
    targets=[(a,c) for a in original.get('actors',[]) for c in a.get('clips',[]) if 'opentoonz_scene' in c]
    if not targets:
        return scene_file, []
    exe=resolve_tcomposer(binary)
    out_dir=Path(out_dir).resolve();base=out_dir/'compiled_opentoonz_scene';base.mkdir(parents=True,exist_ok=True)
    cfg=copy.deepcopy(original);originals=[]
    def copy_input(rel):
        src=resolve_inside(root,rel)
        dst=(base/rel).resolve()
        if dst!=base and base not in dst.parents:
            raise OpenToonzError('Unsafe output asset path: '+rel)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src!=dst:shutil.copy2(src,dst)
        return rel
    for a in cfg['actors']:
        a['source_mask']=copy_input(a['source_mask'])
        for ix,c in enumerate(a['clips']):
            if 'opentoonz_scene' in c:
                if c.get('frames') or c.get('pixelorama_project'):
                    raise OpenToonzError('A clip must use exactly one frame source: OpenToonz, Pixelorama or PNG')
                project_rel=c['opentoonz_scene'];joints_rel=c.get('joints_json')
                if not joints_rel:
                    raise OpenToonzError(a['id']+'/'+c.get('action','?')+': joints_json is required; no fabricated landmarks')
                project=resolve_inside(root,project_rel)
                if project.suffix.lower()!='.tnz':
                    raise OpenToonzError('OpenToonz project must be .tnz')
                joints=resolve_inside(root,joints_rel)
                start=c.get('start_frame',1);count=c.get('frame_count')
                if not (isinstance(start,int) and start>=1 and isinstance(count,int) and 12<=count<=720):
                    raise OpenToonzError('Provide explicit start_frame >=1 and frame_count 12..720 for each .tnz clip')
                maps=load_landmarks(joints,count,a['box'])
                declared=c.get('dependencies',[])
                if not isinstance(declared,list) or not all(isinstance(p,str) for p in declared):
                    raise OpenToonzError('dependencies must be a list of scene-relative asset files')
                # Renderer still uses original .tnz, preserving its OpenToonz project paths.
                sourcepaths=[project_rel,joints_rel]+declared
                for rel in sourcepaths:
                    copy_input(rel)
                    originals.append((root/rel).resolve())
                ident=re.sub('[^A-Za-z0-9_-]','_',str(a['id']))
                name=re.sub('[^A-Za-z0-9_-]','_',str(c.get('action','action')))
                framefolder=base/'poses'/ident/(f'{ix:02d}_'+name)
                frames=render_tnz(exe,project,framefolder,start,count,a['box'],maps)
                c['frames']=[{'png':f.relative_to(base).as_posix(),'joints':p} for f,p in frames]
                c['opentoonz_source']={'scene':project_rel,'joints_json':joints_rel,
                    'source_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),
                    'start_frame':start,'frame_count':count,'dependencies':declared,
                    'render_engine':'tcomposer','alpha_required':True}
                for key in ('opentoonz_scene','joints_json','start_frame','frame_count','dependencies'):
                    c.pop(key,None)
            elif 'pixelorama_project' in c:
                copy_input(c['pixelorama_project'])
                copy_input(c.get('joints_json'))
            else:
                for frame in c.get('frames',[]):
                    if not isinstance(frame,dict) or 'png' not in frame:
                        raise OpenToonzError(a['id']+': authored pose frame must be object with PNG path')
                    copy_input(frame['png'])
    day=cfg.get('day_night',{})
    for key in ('day_background','sky_mask'):
        if day.get(key):copy_input(day[key])
    cfg['opentoonz_integration']={'tool':'OpenToonz tcomposer','alpha_poses':True,
      'manual_joint_maps':True,'character_warp':False,'source':'actual rendered .tnz scenes'}
    dest=base/'scene.compiled.json'
    dest.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),'utf8')
    return dest,sorted(set(originals))
