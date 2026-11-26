#!/usr/bin/env python3
"""Compile real Krita-rendered RGBA PNG animation sequences as full-character poses.

Krita does not provide a documented general headless animation export equivalent
of OpenToonz tcomposer. Artist exports PNG image sequence in Krita GUI first.
Never pretend a .kra itself was rendered by this code; it is kept for provenance.
No pose synthesis, interpolation, transforms, motion from rigid cutouts.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from PIL import Image

class KritaError(ValueError):
    pass


def inside(root, rel, *, directory=False):
    if not isinstance(rel,str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise KritaError('Expected safe scene-relative path: '+repr(rel))
    base=Path(root).resolve();p=(base/rel).resolve()
    if p==base or base not in p.parents:
        raise KritaError('Path outside original scene root: '+str(rel))
    if directory and not p.is_dir():
        raise KritaError('Missing Krita export folder: '+str(p))
    if not directory and not p.is_file():
        raise KritaError('Missing Krita animation asset: '+str(p))
    return p


def get_rendered_frames(folder, prefix, start, count):
    if not isinstance(prefix,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}',prefix):
        raise KritaError('Provide explicit ASCII frame prefix; e.g. frame_')
    lookup={};unexpected=[]
    for p in folder.iterdir():
        if not p.is_file() or p.suffix.lower()!='.png': continue
        if not p.name.startswith(prefix):continue
        m=re.fullmatch(re.escape(prefix)+r'(\d{1,8})\.png',p.name,re.IGNORECASE)
        if not m:
            unexpected.append(p.name)
            continue
        idx=int(m.group(1))
        if idx in lookup:
            raise KritaError('Duplicate numbered Krita frame '+str(idx))
        lookup[idx]=p
    if unexpected:
        raise KritaError('Ambiguous PNG filenames (only prefix+digits.png permitted): '+', '.join(unexpected[:4]))
    wanted=set(range(start,start+count))
    if set(lookup)!=wanted:
        missing=sorted(wanted-set(lookup));extra=sorted(set(lookup)-wanted)
        raise KritaError(f'Krita PNG sequence must be contiguous and exact: missing {missing[:5]}, extra {extra[:5]}')
    return [lookup[i] for i in range(start,start+count)]


def verify_project(path):
    if path.suffix.lower()!='.kra':raise KritaError('Krita source project must be a .kra file')
    if not zipfile.is_zipfile(path): raise KritaError('.kra is not a valid Krita ZIP document')
    with zipfile.ZipFile(path) as f:
        names=set(f.namelist())
        if 'maindoc.xml' not in names or 'mimetype' not in names:
            raise KritaError('.kra is missing Krita document markers')
        if f.read('mimetype').strip()!=b'application/x-krita':
            raise KritaError('Krita project has unexpected mimetype')
    # A .kra is preserved, not parsed to claim these exported PNGs are authentic.
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_rgba_frame(path, size):
    with Image.open(path) as f:
        if f.format!='PNG' or f.mode!='RGBA' or f.size!=size:
            raise KritaError(f'{path.name}: require original RGBA PNG {size} with no resizing/cropping')
        lo,hi=f.getchannel('A').getextrema()
        if hi==0 or lo==255:
            raise KritaError(f'{path.name}: alpha must contain both transparent background and visible painted pose')
        return hashlib.sha256(f.tobytes()).hexdigest()


def compile_scene(scene_file, out_dir, fps=24):
    """Return (compiled_json_path, original_source_files). No-op without Krita clips."""
    src=Path(scene_file).resolve();root=src.parent
    cfg=json.loads(src.read_text('utf-8'))
    targets=[(a,c) for a in cfg.get('actors',[]) for c in a.get('clips',[]) if 'krita_sequence' in c]
    if not targets:return src,[]
    out_dir=Path(out_dir).resolve();base=out_dir/'compiled_krita_scene';base.mkdir(parents=True,exist_ok=True)
    scene=copy.deepcopy(cfg);originals=[]
    def copy_rel(rel):
        source=inside(root,rel); dest=(base/rel).resolve()
        if dest==base or base not in dest.parents:raise KritaError('Invalid compiled output path: '+rel)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if source!=dest: shutil.copy2(source,dest)
        return rel
    for actor in scene['actors']:
        copy_rel(actor['source_mask'])
        for clip in actor['clips']:
            if 'krita_sequence' in clip:
                if any(k in clip for k in ('frames','opentoonz_scene','pixelorama_project')):
                    raise KritaError('Krita clip must have exactly one frame source')
                seq=clip['krita_sequence']
                if not isinstance(seq,dict):raise KritaError('krita_sequence must be an object')
                path=inside(root,seq.get('directory'),directory=True)
                prefix=seq.get('prefix')
                start=seq.get('start_frame',0);count=seq.get('frame_count')
                if type(start) is not int or start<0 or type(count) is not int or not 12<=count<=720:
                    raise KritaError('Krita start_frame>=0 and frame_count 12..720 required')
                if seq.get('fps')!=fps:
                    raise KritaError(f'{actor["id"]}: Krita frame rate {seq.get("fps")} differs from release {fps}; no invented tweening')
                source_project=inside(root,seq.get('source_kra'))
                digest=verify_project(source_project)
                joints_source=inside(root,seq.get('joints_json'))
                from opentoonz_bridge import load_landmarks
                joints=load_landmarks(joints_source,count,actor['box'])
                inputs=get_rendered_frames(path,prefix,start,count)
                size=tuple(map(int,actor['box'][2:]))
                frames=[]
                for i,raw in enumerate(inputs):
                    sha=verify_rgba_frame(raw,size)
                    rel=raw.relative_to(root).as_posix()
                    copy_rel(rel);originals.append(raw)
                    frames.append({'png':rel,'joints':joints[i]})
                for rel in [seq['source_kra'],seq['joints_json']]:
                    copy_rel(rel);originals.append(inside(root,rel))
                support=clip.get('support_sequence')
                if support is not None:
                    if len(support)!=count or any(p not in ('left','right','double','flight') for p in support):
                        raise KritaError('Full-length left/right/double/flight support_sequence required')
                    for frame,s in zip(frames,support):frame['support']=s
                clip['frames']=frames
                clip['krita_source']={
                    'project':seq['source_kra'], 'source_sha256':digest,
                    'frame_count':count,'start_frame':start,'fps':fps,
                    'joints_json':seq['joints_json'],'source_folder':seq['directory'],
                    'prefix':prefix,'original_pixel_sha256':[
                        verify_rgba_frame(raw,size) for raw in inputs],
                    'method':'user-rendered Krita File > Render Animation > PNG Image Sequence',
                    'no_character_deformation':True}
                del clip['krita_sequence']
            elif 'opentoonz_scene' in clip:
                copy_rel(clip['opentoonz_scene']);copy_rel(clip['joints_json'])
                for dep in clip.get('dependencies',[]):copy_rel(dep)
            elif 'pixelorama_project' in clip:
                copy_rel(clip['pixelorama_project']);copy_rel(clip['joints_json'])
            else:
                for frame in clip.get('frames',[]):copy_rel(frame['png'])
    for key in ('day_background','sky_mask'):
        if scene.get('day_night',{}).get(key):copy_rel(scene['day_night'][key])
    scene['krita_integration']={'frame_source':'Krita RGBA image sequence',
      'editor_source':'.kra preserved; PNG sequence supplied by author',
      'tool_did_not_render_kra':True, 'no_deformation':True}
    dest=base/'scene.compiled.json';dest.write_text(json.dumps(scene,ensure_ascii=False,indent=2),'utf-8')
    return dest,sorted(set(originals))


def create_handoff(scene_path,out_dir):
    """Create pixel-exact OpenToonz PNG levels and Pixelorama grids for Krita clips."""
    root=Path(scene_path).resolve().parent; cfg=json.loads(Path(scene_path).read_text('utf-8'))
    out=Path(out_dir).resolve()/'interchange_2d';files=[];entries=[]
    from pixelorama_handoff import _safe,_inside,_save_sheet,_validate_pose_file
    for actor in cfg.get('actors',[]):
        aid=_safe(actor['id']);box=actor['box']
        for i,clip in enumerate(actor.get('clips',[])):
            origin=clip.get('krita_source')
            if not origin:continue
            poses=[_inside(root,f['png']) for f in clip.get('frames',[])]
            if len(poses)!=origin['frame_count']:raise KritaError('Krita pose count changed during pipeline')
            width_height=tuple(map(int,box[2:]))
            for i0,p in enumerate(poses):
                im=_validate_pose_file(p,box)
                sha=hashlib.sha256(im.tobytes()).hexdigest()
                if sha!=origin['original_pixel_sha256'][i0]:
                    raise KritaError('Pixel content changed after Krita RGBA export: '+p.name)
            folder=f'{i:02d}_{_safe(clip.get("action","action"))}'
            lv=out/'opentoonz_levels'/aid/folder;lv.mkdir(parents=True,exist_ok=True)
            for j,p in enumerate(poses,1):
                dest=lv/f'{aid}.{j:04d}.png';shutil.copy2(p,dest);files.append(dest)
            sheet=out/'pixelorama_import'/aid/f'{folder}.png'
            cols,rows=_save_sheet(poses,box,sheet);files.append(sheet)
            entries.append({'actor_id':actor['id'],'action':clip['action'],'origin':'krita',
                'frame_count':len(poses),'fps':origin['fps'], 'cell_size':width_height,
                'source_project_sha256':origin['source_sha256'],
                'pixelorama_sheet':sheet.relative_to(out).as_posix(),
                'opentoonz_level':(lv/f'{aid}.0001.png').relative_to(out).as_posix(),
                'grid':{'columns':cols,'rows':rows,'direction':'row-major'}})
    if entries:
        meta=out/'krita_handoff.json'
        meta.write_text(json.dumps({'schema':1,'entries':entries},ensure_ascii=False,indent=2),'utf-8')
        files.append(meta)
    return files, {'krita_clips':len(entries)}
