"""Bridge to actual external Bitmapflow PNG export. Not an optical-flow generator.
Only exact, non-organic rigid XY translation is eligible for automatic import.
"""
import argparse, json, re, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from quality import load, digest, reduced
from opencv_motion import translation_positions, sequence


def inputs(src, mode):
    frames, times, loop = load(src)
    if len(frames)<3 or not np.all(times>=10) or not np.all(times==np.rint(times)):
        raise ValueError('need >=3 frames with integer durations >=10ms')
    with Image.open(src) as im:
        if mode=='loop' and loop!=0: raise ValueError('infinite loop required')
        if mode=='once' and not (loop is None or (im.format=='PNG' and loop==1)):
            raise ValueError('one-shot only; finite-repeat semantics unsupported')
    positions=translation_positions(frames)
    ends=np.roll(positions,-1,axis=0) if mode=='loop' else positions[1:]
    starts=positions if mode=='loop' else positions[:-1]
    if np.any(np.linalg.norm(ends-starts,axis=1)==0): raise ValueError('held poses are protected')
    return frames,times.astype(int),positions


def prepare(src,out,mode):
    fs,ts,_=inputs(src,mode)
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    for i,f in enumerate(fs): Image.fromarray(f).save(out/f'{i:06d}.png')
    return {'input_directory':str(out),'frames':len(fs),'duration_ms':int(ts.sum()),'mode':mode,
            'original_sha256':[digest(f) for f in fs]}


def read_export(folder):
    files=list(Path(folder).glob('*.png'))
    if not files: raise ValueError('no external PNG frames')
    def index(p):
        m=re.search(r'(\d+)$',p.stem)
        if not m: raise ValueError('export filenames must end in a numeric index')
        return int(m.group(1))
    files=sorted(files,key=index); ids=[index(p) for p in files]
    if ids!=list(range(ids[0],ids[0]+len(ids))): raise ValueError('ambiguous/missing export frame numbers')
    fs=[]
    for p in files:
        with Image.open(p) as im:
            if getattr(im,'n_frames',1)!=1: raise ValueError('individual PNG frames required')
            f=np.array(im.convert('RGBA')); f[f[:,:,3]==0,:3]=0; fs.append(f)
    return fs


def import_export(src,folder,out,mode,factor):
    src,out=Path(src),Path(out)
    if factor not in (2,3,4): raise ValueError('factor must be 2, 3 or 4')
    if out.exists() or out.resolve()==src.resolve() or out.suffix.lower() not in ('.png','.apng'):
        raise ValueError('new lossless APNG path required')
    fs,t,pos=inputs(src,mode); n=len(fs); cyc=mode=='loop'; segments=n if cyc else n-1
    cand=read_export(folder); expected=segments*factor+int(not cyc)
    # Some one-shot exporters append repeated last poses; never extend the original hold.
    if not cyc and len(cand)==n*factor and all(np.array_equal(f,fs[-1]) for f in cand[expected:]):
        cand=cand[:expected]
    if len(cand)!=expected or any(f.shape!=fs[0].shape for f in cand): raise ValueError('export frame count or canvas mismatch')
    if any(not np.array_equal(f,cand[i*factor]) for i,f in enumerate(fs)):
        raise ValueError('original keyframes changed')
    cp=translation_positions(cand); durations=[]; oldsteps=[]; newsteps=[]
    for i in range(segments):
        j=(i+1)%n; a,b=pos[i],pos[j]; step=b-a
        indices=[(i*factor+k)%len(cand) for k in range(factor+1)]
        points=cp[indices]; dif=np.diff(points,axis=0)
        # Exact texture, monotonic segment progression and nearest-pixel linear positions.
        ideal=a+np.arange(factor+1)[:,None]*step/factor
        if np.max(np.abs(points-ideal))>.50001 or np.any(dif@step<=0):
            raise ValueError('new frame off intended trajectory or duplicated')
        oldsteps.append(float(np.linalg.norm(step))); newsteps.extend(np.linalg.norm(dif,axis=1).tolist())
        if max(np.linalg.norm(dif,axis=1))>=oldsteps[-1]-1e-6: raise ValueError('segment does not improve spatial sampling')
        q,r=divmod(int(t[i]),factor)
        d=[q+((k+1)*r//factor-k*r//factor) for k in range(factor)]
        if min(d)<10: raise ValueError('subframe duration below 10ms')
        durations.extend(d)
    if not cyc: durations.append(int(t[-1]))
    # Existing OpenCV LK diagnostics on both sequences; never call low coverage a pass.
    before=sequence([reduced(f) for f in fs],t,cyc)
    after=sequence([reduced(f) for f in cand],np.array(durations),cyc)
    if min(before['tracked_pair_fraction'] or 0,after['tracked_pair_fraction'] or 0)<.8:
        raise ValueError('insufficient OpenCV tracking coverage; visual/manual review required')
    if max(newsteps)>=max(oldsteps): raise ValueError('no measured gain')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        p=Path(tmp)/'candidate.png'; ims=[Image.fromarray(f) for f in cand]
        ims[0].save(p,format='PNG',save_all=True,append_images=ims[1:],duration=durations,loop=0 if cyc else 1,disposal=0,blend=0)
        got,dt,lp=load(p)
        if len(got)!=len(cand) or any(not np.array_equal(a,b) for a,b in zip(got,cand)) or not np.array_equal(dt,durations) or dt.sum()!=t.sum() or lp!=(0 if cyc else 1):
            raise ValueError('APNG verification failed')
        p.replace(out)
    return {'output':str(out),'frames_before':n,'frames_after':len(cand),'duration_ms':int(t.sum()),'max_step_px_before':max(oldsteps),'max_step_px_after':max(newsteps),'relative_max_step_reduction_percent':100*(1-max(newsteps)/max(oldsteps)), 'opencv_before':before,'opencv_after':after,'artistic_quality':None,'source':'external numbered PNG export; provenance must be verified separately'}


def main():
    p=argparse.ArgumentParser(); sp=p.add_subparsers(dest='cmd',required=True)
    for name in ('prepare','import-export'):
        s=sp.add_parser(name); s.add_argument('source'); s.add_argument('directory'); s.add_argument('--mode',choices=['once','loop'],required=True); s.add_argument('--confirm-nonorganic-translation',action='store_true',required=True)
        if name=='import-export': s.add_argument('output'); s.add_argument('--factor',type=int,required=True)
    a=p.parse_args(); result=prepare(a.source,a.directory,a.mode) if a.cmd=='prepare' else import_export(a.source,a.directory,a.output,a.mode,a.factor)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
if __name__=='__main__': main()
