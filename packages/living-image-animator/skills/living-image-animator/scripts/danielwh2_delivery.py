#!/usr/bin/env python3
"""REAL upstream danielwh2 four-view carver -> identical slice-strip -> LIA stack.json.

Runs the authentic source, not a rewritten 4-view approximation. Resulting
stacks can feed existing Three.js raymarch, PixiJS YUKA/Matter, Godot, Blender,
APNG/GIF/FFmpeg exporters when their independent original gates are satisfied.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from PIL import Image
from danielwh2_vendor import install, verify, UpstreamUnavailable

class StackIntegrationError(ValueError): pass

def refuse(msg): raise StackIntegrationError('Official Daniel White Sprite Stacking integration: '+str(msg))

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def extract_original_slices(strip: Path, out_dir: Path, count: int, original: Path):
    with Image.open(strip) as im:
        if im.format!='PNG':refuse('Upstream tool did not produce PNG')
        rgba=im.convert('RGBA')
        if rgba.width%count!=0:refuse('Official strip width is not divisible by requested layer count')
        width,height=rgba.width//count,rgba.height
        if not 8<=width<=512 or not 8<=height<=512:refuse('Original cut width/height outside supported asset range')
        if width*height*count*4>192*1024*1024:refuse('Source stack exceeds 192 MiB uncompressed budget')
        size=max(width,height)
        if size<16:refuse('Source slices are too small for current LIA volume gate')
        layers=[];signatures=set();pixels=0
        left=(size-width)//2;top=(size-height)//2
        for idx in range(count):
            frame=rgba.crop((idx*width,0,(idx+1)*width,height))
            # Center padding adds *transparent* pixels only; never resample/paint sources.
            padded=Image.new('RGBA',(size,size),(0,0,0,0))
            padded.paste(frame,(left,top))
            if padded.crop((left,top,left+width,top+height)).tobytes()!=frame.tobytes():
                refuse('Original carved source RGBA has changed')
            a=padded.getchannel('A')
            pixels+=a.getbbox() is not None
            signatures.add(hashlib.sha256(padded.tobytes()).hexdigest())
            p=out_dir/'layers'/f'{idx:03d}.png'
            p.parent.mkdir(parents=True,exist_ok=True)
            padded.save(p,format='PNG')
            layers.append('layers/'+p.name)
        if pixels<max(4,count//5) or len(signatures)<4:
            refuse('Four-view source did not create a meaningful volume: no real distinct cross-sections')
    cfg={
      'layers':layers,
      'spacing':[1.0,1.0,1.0],
      'pivot':[0.0,0.0,0.0],
      'size':size,
      'author':'Daniel White upstream four-view visual-hull carved input; user source imagery',
      'source':'four-view visual hull approximation; source SHA256='+sha(original),
    }
    p=out_dir/'stack.json';p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),'utf8')
    return p,{'count':count,'w':width,'h':height,'size':size,'unique_slices':len(signatures),
              'source_approximate_hull':True,'unchanged_pixel_regions':True,'stack_sha256':sha(p)}

def generate(views:Path,out:Path,upstream_root:Path,*,count:int=36,fetch=False,order='reading',
             three_module=None,round_=False):
    views=views.expanduser().resolve();out=out.expanduser().resolve()
    if not views.is_file():refuse('Original user-provided four orthographic views PNG missing')
    if out.exists() and any(out.iterdir()):refuse('Output directory must be empty; do not overwrite previous art')
    if not 8<=count<=96:refuse('Choose 8–96 source carve layers; not a fake image extrusion')
    with Image.open(views) as im:
        if im.format!='PNG' or im.width>4096 or im.height>4096:refuse('Original source must be a PNG <=4096 in each dimension')
    try:
        upstream_root,upstream=install(upstream_root,fetch=fetch)
    except UpstreamUnavailable as e:
        refuse(str(e))
    upstream_script=upstream_root/'skills/sprite-stacking/scripts/views_to_slices.py'
    out.mkdir(parents=True,exist_ok=True)
    strip=out/'slices_strip.png'
    check=out/'original_four_view_preview.png'
    html=out/'original_sprite_stack_viewer.html'
    cmd=[sys.executable,str(upstream_script),str(views),str(strip),
         '--slices',str(count),'--order',order,
         '--colours','0','--shade','0','--dark-thresh','0',
         '--preview',str(check),'--html',str(html)]
    if round_:cmd.append('--round')
    completed=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180,check=False)
    if completed.returncode:
        refuse('Official views_to_slices.py failed: '+(completed.stderr or completed.stdout)[-700:])
    if not strip.is_file() or not html.is_file() or not check.is_file():
        refuse('Official tool returned without real strip/preview/HTML outputs')
    stack,info=extract_original_slices(strip,out,count,views)
    licensed=upstream_root/'LICENSE';shutil.copyfile(licensed,out/'LICENSE.danielwh2.txt')
    shutil.copyfile(views,out/'original_four_views.png')
    asset=None
    if three_module:
        # Reuse the already installed REAL Three.js/GLSL volume viewer.
        preview=Path(__file__).with_name('sprite_stack_asset_preview.py')
        if not preview.is_file():refuse('Previous real Three.js sprite-stack bridge missing')
        target=out/'threejs_360_volume.html'
        step=subprocess.run([sys.executable,str(preview),'--stack',str(stack),'--out',str(target),
          '--three-js',str(Path(three_module).expanduser().resolve())],
          capture_output=True,text=True,timeout=180,check=False)
        if step.returncode or not target.is_file():
            refuse('Previous original Three.js volume viewer could not render stack: '+step.stderr[-500:])
        asset=target
    manifest={'engine':'authentic danielwh2/sprite-stacking views_to_slices.py',
      'upstream':upstream,'input_sha256':sha(views),'carving':'visual-hull estimated from actual 4 views',
      'original_painted_poses_unchanged':True,'actor_motion_gate_bypassed':False,
      'standalone_viewer_offline':True,'threejs_volume':bool(asset),**info}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    zpath=out.parent/(out.name+'_sprite_stacking.zip')
    if zpath.exists():refuse('ZIP output already exists; choose an empty destination')
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():z.write(f,('sprite_stacking/'+f.relative_to(out).as_posix()))
    with zipfile.ZipFile(zpath) as z:
        if z.testzip() is not None:refuse('Created package is corrupt')
    return {'zip':str(zpath),'stack':str(stack),'official_viewer':str(html),
            'threejs_viewer':str(asset) if asset else None,**info}

def main():
    ap=argparse.ArgumentParser(description='Official danielwh2 Sprite Stacking -> Living Image Animator source-compatible volume')
    ap.add_argument('views',type=Path,help='One user-authored PNG with TOP, SIDE, FRONT, BACK')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--upstream-root',type=Path,default=Path(__file__).parents[1]/'vendor/danielwh2')
    ap.add_argument('--install-upstream',action='store_true',help='Download official hash-pinned source when network permits')
    ap.add_argument('--slices',type=int,default=36)
    ap.add_argument('--order',choices=['auto','reading'],default='reading')
    ap.add_argument('--round',action='store_true')
    ap.add_argument('--three-js',type=Path,help='Use existing genuine local Three.js ESM for additional 360 raymarch')
    a=ap.parse_args()
    print(json.dumps(generate(a.views,a.out,a.upstream_root,count=a.slices,
        fetch=a.install_upstream,order=a.order,round_=a.round,three_module=a.three_js),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
