"""FFmpeg candidate export with exact decoded RGBA and timing guard."""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import quality

def run(args, timeout=120):
    p=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError(f'{Path(args[0]).name}: {p.stderr[-1600:]}')
    return p.stdout

def sha(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def optimize(src,dst,allow_webp=False,flow=False):
    src,dst=Path(src).resolve(),Path(dst).resolve()
    if src==dst or dst.exists(): raise ValueError('new output path required')
    with Image.open(src) as im:
        fmt=im.format
        if fmt not in ('GIF','PNG') or im.n_frames<2 or im.info.get('default_image'): raise ValueError('animated GIF or APNG without separate poster required')
        if im.width*im.height*im.n_frames>80_000_000: raise ValueError('decoded pixel budget exceeded')
    ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe')
    if not ffmpeg or not ffprobe: raise RuntimeError('real FFmpeg and FFprobe required')
    original_hash=sha(src); fs,t,loop=quality.load(src)
    if not np.all(np.isfinite(t)) or not np.all(t>0) or not np.array_equal(t,np.round(t)): raise ValueError('positive integer-ms timing required')
    ext=dst.suffix.lower()
    if ext=='.gif':
        if fmt!='GIF' or np.any(t%10) or t[-1]>655350: raise ValueError('same-format GIF, centisecond timing required')
        if loop is not None and not 0<=loop<=65535: raise ValueError('unsupported loop count')
    elif ext=='.webp':
        if not allow_webp or loop!=0 or np.any(t<20): raise ValueError('WebP requires explicit runtime support, infinite loop and >=20 ms frames')
    else: raise ValueError('output must be GIF or WebP')
    probe=json.loads(run([ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,time_base','-of','json',str(src)]))
    if len(probe.get('streams',[]))!=1: raise ValueError('one video stream required')
    dst.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as td:
        tmp=Path(td)/('candidate'+ext)
        cmd=[ffmpeg,'-nostdin','-v','error','-n','-ignore_loop','1']
        if fmt=='GIF': cmd+=['-min_delay','0']
        cmd+=['-i',str(src),'-an','-sn','-dn','-filter_complex_threads','1','-threads','1']
        if ext=='.gif':
            cmd+=['-filter_complex','[0:v]split[a][b];[a]palettegen=reserve_transparent=1:stats_mode=full[p];[b][p]paletteuse=dither=none:alpha_threshold=128','-fps_mode','passthrough','-loop',str(-1 if loop is None else loop),'-final_delay',str(int(t[-1]//10))]
        else:
            cmd+=['-c:v','libwebp_anim','-lossless','1','-quality','75','-compression_level','3','-pix_fmt','bgra','-fps_mode','passthrough','-loop','0']
        run(cmd+[str(tmp)])
        with Image.open(tmp) as im:
            if im.format!=('GIF' if ext=='.gif' else 'WEBP') or im.n_frames!=len(fs) or im.size!=(fs[0].shape[1],fs[0].shape[0]): raise ValueError('format/frame count/canvas changed')
        new,dt,newloop=quality.load(tmp)
        if not np.array_equal(t,dt) or loop!=newloop: raise ValueError('timing/repeat semantics changed')
        if any(not np.array_equal(f,g) for f,g in zip(fs,new)): raise ValueError('visible RGBA/alpha changed')
        if sha(src)!=original_hash: raise ValueError('source changed')
        before,after=src.stat().st_size,tmp.stat().st_size
        if after>=before: raise ValueError('no file size gain')
        metrics=None
        if flow:
            a,b=quality.audit(src,flow=True),quality.audit(tmp,flow=True)
            a.pop('file');b.pop('file')
            if a!=b: raise ValueError('OpenCV re-audit differs')
            metrics=a
        os.link(tmp,dst)
    return dict(source=str(src),output=str(dst),ffmpeg=run([ffmpeg,'-version']).splitlines()[0],source_sha256=original_hash,source_bytes=before,output_bytes=after,reduction_percent=100*(before-after)/before,frames=len(fs),duration_ms=float(t.sum()),exact_visible_rgba=True,exact_timeline=True,exact_repeat_metadata=True,flow_reaudit=metrics,artistic_improvement_percent=None,source_probe=probe['streams'][0])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('output');p.add_argument('--allow-webp',action='store_true');p.add_argument('--flow',action='store_true');a=p.parse_args()
    try: print(json.dumps(optimize(a.source,a.output,a.allow_webp,a.flow),ensure_ascii=False,indent=2,allow_nan=False))
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as e: p.exit(1,f'REJECTED: {e}\n')
if __name__=='__main__': main()
