#!/usr/bin/env python3
"""Bridge official sprite-in-the-round and META GAMES actual RGBA sprite stacks.

Inputs: author-approved stack.json, official slice-strip PNG, four-view art, or static GLB.
Outputs: real independent bottom-to-top RGBA PNG layers + stack.json + upstream GLB/OBJ,
16-direction sprites / GIF / optional VOX, plus existing offline Three.js WebGL2 volume HTML.
All outputs are derivatives; never replace source assets or claim recovered engine gameplay.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
from PIL import Image, PngImagePlugin
from install_upstream import COMMIT, UPSTREAM, resolve as resolve_upstream

HERE=Path(__file__).resolve().parent
PLUGINS=HERE.parent.parent
OLD_FOUR=PLUGINS/'sprite-stacking-four-views'/'scripts'/'views_to_stack.py'
OLD_GLB=PLUGINS/'sprite-stacking-priority'/'scripts'/'stack_from_glb.py'
OLD_VIEWER=PLUGINS/'sprite-stacking-priority'/'scripts'/'stack_to_html.py'
MULTIVIEWS=HERE/'build_from_views.py'
MAX_BYTES=128*1024*1024
MAX_IMG_PIXELS=18_000_000
MAX_LAYERS=192


def safe_vec3(values, desc, positive=False):
    if not isinstance(values,(list,tuple)) or len(values)!=3:
        raise ValueError(desc+' needs three numbers')
    try: arr=[float(x) for x in values]
    except (ValueError,TypeError) as exc: raise ValueError(desc+' contains invalid numbers') from exc
    if not all(math.isfinite(v) for v in arr) or (positive and any(x<=0 for x in arr)):
        raise ValueError(desc+' contains nonfinite or nonpositive values')
    return arr


def inspect_png(path:Path) -> tuple[int,int,dict]:
    if path.is_symlink():raise ValueError('Input PNG symlink not permitted')
    with Image.open(path) as im:
        if im.format!='PNG':raise ValueError('Expected a genuine PNG image')
        w,h=im.size
        if min(w,h)<1 or w*h>MAX_IMG_PIXELS or w>65536 or h>8192:
            raise ValueError('PNG pixel/dimension budget exceeded')
        return w,h,dict(im.info)


def stack_to_strip(manifest:Path, target:Path) -> tuple[int,list[float]]:
    """Losslessly repack our authored bottom-first PNG layers into official slice sheet."""
    obj=json.loads(manifest.read_text(encoding='utf-8'))
    layers=obj.get('layers')
    if not isinstance(layers,list) or not layers or len(layers)>MAX_LAYERS or len(set(layers))!=len(layers):
        raise ValueError('stack.json needs 1..192 unique layers')
    spacing=safe_vec3(obj.get('spacing'), 'spacing',positive=True)
    pivot=safe_vec3(obj.get('pivot',[0,0,0]), 'pivot')
    images=[];w=h=None;opaque=0
    for item in layers:
        if not isinstance(item,str) or not item.lower().endswith('.png'):
            raise ValueError('Layer entries must be PNG paths')
        p=manifest.parent/item
        if p.is_symlink():raise ValueError('Symlinked layer forbidden')
        p=p.resolve(strict=True)
        if manifest.parent not in p.parents:raise ValueError('Layer path escapes stack')
        with Image.open(p) as im:
            if im.format!='PNG' or im.mode!='RGBA':raise ValueError('Each author slice must be RGBA PNG')
            if w is None:w,h=im.size
            if im.size!=(w,h) or w>512 or h>512:raise ValueError('Inconsistent or oversized layer dimensions')
            copy=im.copy()
            opaque+=sum(a>=128 for a in copy.getchannel('A').tobytes())
            images.append(copy)
    if not opaque:raise ValueError('No occupied voxels in supplied stack')
    if w*h*len(images)*4>MAX_BYTES:raise ValueError('Stack RGBA budget exceeded')
    sheet=Image.new('RGBA',(w*len(images),h))
    for i,im in enumerate(images):sheet.paste(im,(i*w,0))
    pngmeta=PngImagePlugin.PngInfo();pngmeta.add_text('slices',str(len(images)));pngmeta.add_text('frames','1')
    target.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(target,pnginfo=pngmeta,optimize=True)
    return len(images),spacing


def strip_to_stack(sheet:Path, destination:Path, count:int|None, frames:int|None, ppm:float, source:Path) -> tuple[Path,Path|None,int,int]:
    """Official bottom-left-first horizontal slice sheet -> our bottom-first stack.json.

    Frames (if any) are separate full pose volumes with the same pivot/spacing.
    Never reinterpret a flat sheet without explicit count/embedded 'slices'.
    """
    width,height,meta=inspect_png(sheet)
    n=count or (int(meta['slices']) if str(meta.get('slices','')).isdigit() else None)
    f=frames or (int(meta['frames']) if str(meta.get('frames','')).isdigit() else 1)
    if n is None or n<1 or n>MAX_LAYERS or f<1 or f>24:
        raise ValueError('Sheet needs 1..192 slices and 1..24 authored full pose frames')
    if width%n or height%f:
        raise ValueError('Sheet dimensions not divisible by layer/frame count')
    w=width//n;h=height//f
    if w>512 or h>512 or w*h*n*f*4>MAX_BYTES:
        raise ValueError('Volume exceeds browser/WebGL2 CPU texture limits')
    with Image.open(sheet) as im:
        im.load(); whole=im.convert('RGBA')
    if not any(a>=128 for a in whole.getchannel('A').tobytes()):
        raise ValueError('No visible pixels in slice volume')
    hashval=hashlib.sha256(sheet.read_bytes()).hexdigest()
    manifests=[]
    for frame in range(f):
        path=destination/(f'pose_{frame:03d}' if f>1 else '')
        layer_dir=path/'layers';layer_dir.mkdir(parents=True,exist_ok=False)
        names=[];filled=0
        for z in range(n):
            tile=whole.crop((z*w,frame*h,(z+1)*w,(frame+1)*h))
            filled+=sum(a>=128 for a in tile.getchannel('A').tobytes())
            name=f'layers/{z:03d}.png';tile.save(path/name,optimize=True);names.append(name)
        if not filled: raise ValueError(f'Pose {frame} contains no occupied voxels')
        # Our consistent frame coordinate axes: X-right, Y-forward, Z-up.
        info={'format':'sprite-stacking-grunge/1','source_sha256':hashval,
              'source_sheet':str(sheet),'source_type':'sprite-in-the-round-slice-sheet',
              'layers':names,'spacing':[1/ppm,1/ppm,1/ppm],'pivot':[0,0,0],
              'size':384,'axes':'X-right Y-forward (top row) Z-up; bottom slice first',
              'voxel_grid':[w,h,n],'occupied_voxels':filled,'pose_index':frame,
              'interoperability':'sprite-in-the-round / META GAMES',
              'not_gameplay':True}
        dest=path/'stack.json';dest.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8');manifests.append(dest)
    if f>1:
        scene={'stacks':[{'stack':str(manifests[0].relative_to(destination.parent)),
              'frames':[str(p.relative_to(destination.parent)) for p in manifests[1:]],
              'fps':8,'position':[0,0,0],'scale':[1,1,1],'rotation':[0,0,0]}]}
        scene_path=destination.parent/'scene-stacks.json'
        scene_path.write_text(json.dumps(scene,ensure_ascii=False,indent=2),encoding='utf-8')
    else: scene_path=None
    return manifests[0],scene_path,n,f


def use_existing(what:Path,out:Path,args,upstream:Path) -> Path:
    if what.name=='stack.json' and what.suffix.lower()=='.json':
        return what
    if what.is_dir() and (what/'stack.json').is_file():
        return what/'stack.json'
    if what.is_dir() and (what/'top.png').is_file() and (what/'side.png').is_file():
        result=out/'native-view-slices.png'
        subprocess.run([sys.executable,str(MULTIVIEWS),str(what),'--out',str(result),
                        '--upstream-root',str(upstream)],check=True,timeout=600)
        return result
    if what.suffix.lower()=='.glb' and what.is_file():
        if not OLD_GLB.is_file():raise RuntimeError('Existing static GLB → slices converter missing')
        target=out/'source-glb-slices'
        cmd=[sys.executable,str(OLD_GLB),str(what),'--out',str(target),
             '--xy',str(args.xy),'--z',str(args.z)]
        if args.allow_shell:cmd+=['--allow-shell']
        subprocess.run(cmd,check=True,timeout=1500)
        return target/'stack.json'
    if args.four_views:
        if what.suffix.lower()!='.png':raise ValueError('--four-views expects original 4-view PNG')
        if not OLD_FOUR.is_file():raise RuntimeError('Existing pinned 4-view carver missing')
        target=out/'four-view-slices'
        cmd=[sys.executable,str(OLD_FOUR),str(what),'--out',str(target),
             '--slices',str(args.slices),'--no-html']
        if args.no_install_upstream:cmd+=['--no-install-upstream']
        subprocess.run(cmd,check=True,timeout=650)
        return target/'stack-data'/'stack.json'
    if what.suffix.lower()=='.png':
        return what
    raise ValueError('Input must be stack.json, stack folder, authorized static GLB, or slice-strip PNG; use --four-views for aligned 4-view art')


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--upstream-root',help='Existing official sprite-in-the-round source directory')
    ap.add_argument('--no-install-upstream',action='store_true')
    ap.add_argument('--count',type=int,help='Slice count for unannotated upstream slice strip')
    ap.add_argument('--frames',type=int,help='Frame count for authored animation strips')
    ap.add_argument('--ppm',type=float,help='Override art pixels per metre; defaults to 16 for native strips or 1/spacing for stack.json')
    ap.add_argument('--dirs',type=int,choices=[0,4,8,16,32],default=16)
    ap.add_argument('--gif',action='store_true',help='Export official animated turntable GIF')
    ap.add_argument('--vox',action='store_true',help='Export official MagicaVoxel VOX')
    ap.add_argument('--four-views',action='store_true',help='Carve 4 orthographic views using previously installed first OSS')
    ap.add_argument('--slices',type=int,default=64,help='Vertical carving resolution for 4-view input')
    ap.add_argument('--xy',type=int,default=192,help='GLB slice XY grid budget')
    ap.add_argument('--z',type=int,default=96,help='GLB slice height grid budget')
    ap.add_argument('--allow-shell',action='store_true')
    ap.add_argument('--no-html',action='store_true',help='Only create real assets; no Three.js HTML')
    ap.add_argument('--no-install-js',action='store_true',help='Require locally cached pinned Three.js/esbuild')
    args=ap.parse_args()
    if args.ppm is not None and (not math.isfinite(args.ppm) or not 0<args.ppm<=1024):
        ap.error('--ppm must be a finite number 0..1024')
    if not 4<=args.slices<=192 or not 16<=args.xy<=384 or not 8<=args.z<=192:
        ap.error('Slice/GLB grid limit exceeded')
    source=args.source.expanduser().resolve(strict=True)
    out=args.out.expanduser().resolve()
    source_root=source if source.is_dir() else (source.parent if source.name=='stack.json' else None)
    if out==source or (source_root is not None and (out==source_root or source_root in out.parents or out in source_root.parents)):
        raise ValueError('Output must be disjoint from original stack/source; no overwrite')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be a new empty directory')
    if source.is_file() and out==source.parent:
        raise ValueError('Output directory must differ from source file folder')
    # Resolve tools before creating any output. Uses actual pinned source if necessary.
    upstream=resolve_upstream(args.upstream_root,no_install=args.no_install_upstream)
    if not OLD_VIEWER.is_file():raise RuntimeError('Original META GAMES Three.js volume renderer missing')
    out.mkdir(parents=True,exist_ok=True)
    upstream_input=use_existing(source,out,args,upstream)
    if upstream_input.name=='stack.json':
        native_sheet=out/'native-slices.png'
        count,spacing=stack_to_strip(upstream_input,native_sheet)
        # Upstream GLB exporter assumes isotropic art pixels. Avoid quietly warping
        # the source's geometry when original per-axis spacing is unequal.
        if max(spacing)-min(spacing)>max(spacing)*1e-5:
            raise ValueError('Anisotropic stack spacing requires original WebGL2 volume viewer; upstream GLB would distort it')
        ppm=args.ppm if args.ppm is not None else 1.0/spacing[0]
        if ppm>1024:raise ValueError('Source stack spacing too small for upstream pixels-per-metre limit')
        frames=1
        new_stack=upstream_input; scene=None
    else:
        native_sheet=upstream_input
        ppm=args.ppm if args.ppm is not None else 16.0
        new_stack,scene,count,frames=strip_to_stack(native_sheet,out/'stacks',args.count,args.frames,ppm,source)
    export=out/'exports'
    cmd=[sys.executable,str(upstream/'scripts'/'stack.py'),str(native_sheet),
         '--out',str(export),'--name','sprite_stack',
         '--count',str(count),'--frames',str(frames),
         '--ppm',str(ppm),'--dirs',str(args.dirs)]
    if args.gif:cmd+=['--gif']
    if args.vox:cmd+=['--vox']
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=1200)
    if proc.returncode:
        raise RuntimeError('Official sprite-in-the-round exporter failed: '+(proc.stderr or proc.stdout)[-2500:])
    try:result=json.loads(proc.stdout)
    except (ValueError,TypeError) as e:raise RuntimeError('Official exporter did not return the documented JSON result') from e
    if not isinstance(result.get('files'),dict):raise RuntimeError('Official exporter result lacks files')
    if frames==1 and ('glb' not in result['files'] or not (export/'sprite_stack.glb').is_file()):
        raise RuntimeError('Official exporter did not produce expected original-volume GLB')
    path=out/'sprite-stacking.html'
    if not args.no_html:
        cmd=[sys.executable,str(OLD_VIEWER),str(scene or new_stack),'--out',str(path)]
        if args.no_install_js:cmd+=['--no-install']
        subprocess.run(cmd,check=True,timeout=600)
    record={'source':str(source),'upstream':UPSTREAM,'upstream_commit':COMMIT if not args.upstream_root else 'EXPLICIT_LOCAL_SOURCE',
            'upstream_exports':result.get('files',{}),'stack':str(new_stack),'authored_animation_frames':frames,
            'volume_html':str(path) if not args.no_html else None,'not_gameplay':True}
    (out/'sprite-in-the-round.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SPRITE_IN_THE_ROUND:',export,'real bottom-first slices:',count,'frames:',frames)
    if not args.no_html:print('META GAMES VOLUME HTML:',path)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        sys.exit('ERROR: '+str(exc))
