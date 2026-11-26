#!/usr/bin/env python3
"""Pixelorama .pxo -> strict v0.5 hand-authored full-pose sprites.

Pixelorama is a separately installed MIT-licensed executable, not bundled here.
No figure generation, interpolation, warping or automatic motion guessing.
CLI: Pixelorama --headless --quit -- PROJECT.pxo --framecount
CLI: Pixelorama --headless --quit -- PROJECT.pxo --spritesheet --export --output OUT.png
Only frame-authored PNGs plus externally verified joint annotations enter the animator.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, re, shutil, subprocess
from pathlib import Path
from PIL import Image

class PixeloramaError(ValueError):
    pass


def resolve_inside(root: Path, raw: str) -> Path:
    if not isinstance(raw,str) or not raw or Path(raw).is_absolute():
        raise PixeloramaError('Source path must be relative to scene.json: '+repr(raw))
    base=root.resolve(); p=(base/raw).resolve()
    if base!=p and base not in p.parents:
        raise PixeloramaError('Source path escapes scene directory: '+raw)
    if not p.is_file(): raise PixeloramaError('Missing input: '+str(p))
    return p


def binary_path(explicit=None):
    selected=explicit or os.environ.get('PIXELORAMA_BIN')
    if selected:
        found=shutil.which(selected) or (str(Path(selected).expanduser().resolve()) if Path(selected).expanduser().is_file() else None)
    else:
        found=next((shutil.which(x) for x in ('pixelorama','Pixelorama.x86_64','Pixelorama') if shutil.which(x)),None)
    if not found:
        raise PixeloramaError('Pixelorama executable not found. Install Pixelorama >=1.2.4, then use --pixelorama /path/to/Pixelorama or PIXELORAMA_BIN')
    return str(Path(found).resolve())



def require_supported_version(binary):
    """Pixelorama 1.2.4 fixed CLI --output; earlier binaries are unsafe for automation."""
    try:
        result=subprocess.run([binary,'--headless','--quit','--','--pixelorama-version'],
                              capture_output=True,text=True,timeout=30,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise PixeloramaError('Pixelorama version probe failed: '+str(e)) from e
    report=(result.stdout or '')+'\n'+(result.stderr or '')
    version=re.search(r'(?:^|\b)v?(\d+)\.(\d+)\.(\d+)(?:\b|$)', report)
    if result.returncode!=0 or not version:
        raise PixeloramaError('Cannot verify installed Pixelorama version from CLI output: '+report[-1000:])
    parsed=tuple(int(version.group(i)) for i in (1,2,3))
    if parsed<(1,2,4):
        raise PixeloramaError('Pixelorama >= 1.2.4 required for reliable --output; found '+'.'.join(map(str,parsed)))
    return parsed

def run_cli(binary, project, *args):
    cmd=[binary,'--headless','--quit','--',str(project),*args]
    try:
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=90,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise PixeloramaError('Pixelorama command failed: '+str(e)) from e
    if result.returncode!=0:
        raise PixeloramaError('Pixelorama exited %d while processing %s: %s' %
                              (result.returncode,project.name,(result.stderr or result.stdout)[-1800:]))
    return (result.stdout or '')+'\n'+(result.stderr or '')


def frame_count(binary, project):
    output=run_cli(binary,project,'--framecount')
    vals=re.findall(r'^\s*(\d{1,6})\s*$',output,re.M)
    if not vals: raise PixeloramaError('Could not parse Pixelorama --framecount output: '+output[-1500:])
    count=int(vals[-1])
    if count<12 or count>720: raise PixeloramaError('Expected 12-720 authored project frames, got '+str(count))
    return count


def parse_poses_landmarks(json_path, count, size):
    data=json.loads(json_path.read_text('utf-8'))
    records=data.get('frames') if isinstance(data,dict) else data
    if not isinstance(records,list) or len(records)!=count:
        raise PixeloramaError('Joint landmarks must supply exactly %d individually annotated frames: %s'%(count,json_path))
    w,h=size
    for i,landmarks in enumerate(records):
        if not isinstance(landmarks,dict) or 'root' not in landmarks:
            raise PixeloramaError(f'Missing root joint in {json_path.name} frame {i}')
        if len(landmarks)<3:
            raise PixeloramaError(f'Minimum two anatomical joints + root in {json_path.name} frame {i}')
        for j,xy in landmarks.items():
            if not (isinstance(xy,list) and len(xy)==2 and all(isinstance(v,(int,float)) for v in xy) and
                    0<=xy[0]<w and 0<=xy[1]<h):
                raise PixeloramaError(f'Invalid {j} joint in frame {i}, expected local sprite coordinates')
    return records


def export_project(binary, project, out_dir, box, joint_json):
    count=frame_count(binary,project)
    out_dir.mkdir(parents=True,exist_ok=True)
    sheet=out_dir/'pixelorama_sheet.png'
    if sheet.exists(): sheet.unlink()  # never trust a leftover export on CLI failure
    run_cli(binary,project,'--spritesheet','--export','--direction','0','--output',str(sheet))
    if not sheet.is_file() or sheet.stat().st_size<32:
        raise PixeloramaError('Pixelorama did not export spritesheet. CLI --output requires Pixelorama >=1.2.4')
    _,_,w,h=map(int,box)
    if w<=0 or h<=0: raise PixeloramaError('Invalid actor box')
    landmarks=parse_poses_landmarks(joint_json,count,(w,h))
    frames=[]
    with Image.open(sheet) as raw:
        width,height=raw.size
        if width%w or height%h:
            raise PixeloramaError(f'Pixelorama sprite cell {w}x{h} does not fit sheet {width}x{height}; the .pxo canvas must equal actor box')
        cols,rows=width//w,height//h
        if cols*rows<count: raise PixeloramaError('Pixelorama exported fewer sprite cells than --framecount')
        if cols*rows>count and rows>1 and count <= cols:
            raise PixeloramaError('Ambiguous Pixelorama spritesheet layout; use one compact exported frame grid')
        rgba=raw.convert('RGBA')
        for i in range(count):
            x,y=(i%cols)*w,(i//cols)*h
            crop=rgba.crop((x,y,x+w,y+h))
            if not crop.getchannel('A').getbbox():
                raise PixeloramaError(f'Pixelorama exported an invisible pose #{i}; draw a complete character on every cel')
            dest=out_dir/f'pose_{i:04d}.png'
            crop.save(dest)
            frames.append((dest,landmarks[i]))
    return frames


def compile_scene(scene_path:Path, out_dir:Path, pixelorama_executable=None):
    """Compile author-made .pxo clips to the exact v0.5 PNG frame schema.

    All input paths stay relative to original scene. A self-contained generated scene
    plus original Pixelorama files are put under output/compiled_scene.
    """
    scene_path=Path(scene_path).resolve();orig=scene_path.parent
    original=json.loads(scene_path.read_text('utf-8'))
    if not any('pixelorama_project' in c for a in original.get('actors',[]) for c in a.get('clips',[])):
        return scene_path
    bin=binary_path(pixelorama_executable)
    require_supported_version(bin)
    compiled=Path(out_dir).resolve()/'compiled_scene'
    compiled.mkdir(parents=True,exist_ok=True)
    scene=copy.deepcopy(original)
    scene['pixelorama_integration']={'schema':1,'tool':'Pixelorama', 'provenance':'PNG authored manually in Pixelorama .pxo',
                                     'character_deformation':False}
    def copy_file(raw):
        src=resolve_inside(orig,raw); tgt=compiled/raw
        tgt.parent.mkdir(parents=True,exist_ok=True)
        if src!=tgt.resolve(): shutil.copy2(src,tgt)
        return str(tgt.relative_to(compiled).as_posix())
    # registered original inputs used by native pose compositor
    for actor in scene['actors']:
        actor['source_mask']=copy_file(actor['source_mask'])
        for index,clip in enumerate(actor['clips']):
            if 'pixelorama_project' in clip:
                if clip.get('frames'):
                    raise PixeloramaError('Do not mix authored PNG frames and pixelorama_project in the same clip')
                project_raw=clip['pixelorama_project'];landmarks_raw=clip.get('joints_json')
                if not landmarks_raw: raise PixeloramaError(actor['id']+'/'+clip.get('action','')+': joints_json required, landmarks cannot be fabricated')
                source_project=resolve_inside(orig,project_raw)
                src_joints=resolve_inside(orig,landmarks_raw)
                # Preserve the actual editable .pxo and original landmark annotations
                project_rel=copy_file(project_raw);joints_rel=copy_file(landmarks_raw)
                ident=re.sub('[^A-Za-z0-9_-]','_',str(actor['id']))
                action=re.sub('[^A-Za-z0-9_-]','_',str(clip.get('action','action')))
                dst=compiled/'poses'/ident/(f'{index:02d}_'+action)
                exported=export_project(bin,source_project,dst,actor['box'],src_joints)
                clip['frames']=[{'png':p.relative_to(compiled).as_posix(),'joints':j} for p,j in exported]
                clip['pixelorama_source']={'project':project_rel,'joints_json':joints_rel,
                    'source_sha256':hashlib.sha256(source_project.read_bytes()).hexdigest(),'frame_count':len(exported)}
                del clip['pixelorama_project'];del clip['joints_json']
            else:
                for frame in clip.get('frames',[]):
                    if isinstance(frame,dict) and 'png' in frame:frame['png']=copy_file(frame['png'])
    day=scene.get('day_night',{})
    for field in ('day_background','sky_mask'):
        if day.get(field):day[field]=copy_file(day[field])
    dest=compiled/'scene.compiled.json'
    dest.write_text(json.dumps(scene,ensure_ascii=False,indent=2),'utf-8')
    return dest


def main():
    p=argparse.ArgumentParser(description='Compile Pixelorama .pxo animations into full-frame, source-locked pose sprites')
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pixelorama',default=None)
    a=p.parse_args()
    path=compile_scene(a.scene,a.out,a.pixelorama)
    print(json.dumps({'compiled_scene':str(path),'pixelorama_used':path!=a.scene.resolve()},ensure_ascii=False))

if __name__=='__main__':main()
