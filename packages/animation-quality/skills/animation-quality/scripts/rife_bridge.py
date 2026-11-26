"""Optional actual upstream RIFE CLI; opaque nonorganic effect previews only."""
import argparse, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy import ndimage
from PIL import Image
from quality import load, reduced, delta, digest
from opencv_motion import sequence


def source(path, mode, factor):
    fs,t,loop=load(path)
    if len(fs)<3 or len(fs)>256 or max(fs[0].shape[:2])>1024:
        raise ValueError('3–256 frames, maximum canvas side 1024')
    if any(f.shape!=fs[0].shape or not np.all(f[:,:,3]==255) for f in fs):
        raise ValueError('opaque effects only; transparent sprites route to Bitmapflow or source render')
    if not np.all(t==np.rint(t)) or np.any(t<10): raise ValueError('invalid durations')
    with Image.open(path) as im:
        if mode=='loop' and loop!=0: raise ValueError('infinite loop required')
        if mode=='once' and not (loop is None or (im.format=='PNG' and loop==1)): raise ValueError('one-shot required')
    n=len(fs) if mode=='loop' else len(fs)-1
    if np.any(t[:n]<factor*10): raise ValueError('insufficient timing budget')
    if any(np.array_equal(fs[i],fs[(i+1)%len(fs)]) for i in range(n)):
        raise ValueError('held poses or duplicate loop endpoint require manual route')
    return fs,t.astype(int)


def edge_energy(a):
    gray=a[:,:,:3].astype(np.float32).mean(axis=2)/255
    return float(np.mean(np.hypot(ndimage.sobel(gray,axis=0),ndimage.sobel(gray,axis=1))))


def assess(fs,t,cand,mode,factor):
    cyc=mode=='loop'; n=len(fs); segments=n if cyc else n-1
    if len(cand)!=segments*factor+int(not cyc): raise ValueError('wrong frame count')
    if any(f.shape!=fs[0].shape or f.dtype!=np.uint8 or not np.all(f[:,:,3]==255) for f in cand): raise ValueError('bad frame format')
    if any(not np.array_equal(f,cand[i*factor]) for i,f in enumerate(fs)): raise ValueError('keyframe changed')
    a=[reduced(f) for f in fs]; b=[reduced(f) for f in cand]; durations=[]; oldsteps=[]; newsteps=[]
    for i in range(segments):
        j=(i+1)%n; k=i*factor
        old=delta(a[i],a[j]); oldsteps.append(old)
        ids=[(k+m)%len(cand) for m in range(factor+1)]
        steps=[delta(b[u],b[v]) for u,v in zip(ids,ids[1:])]
        if old<=.0001 or min(steps)<=.0001 or max(steps)>=.99*old: raise ValueError('no per-segment pixel-step improvement')
        newsteps.extend(steps)
        # SciPy edge-energy proxy catches excessive smoothing or invented high-frequency texture.
        ea,eb=edge_energy(fs[i]),edge_energy(fs[j]); low=min(ea,eb); high=max(ea,eb)
        for idx in ids[1:-1]:
            e=edge_energy(cand[idx])
            if e<.7*low or e>1.3*high+.001: raise ValueError('edge-energy regression; visual review required')
        q,r=divmod(int(t[i]),factor)
        durations.extend(q+(m+1)*r//factor-m*r//factor for m in range(factor))
    if not cyc: durations.append(int(t[-1]))
    before=sequence(a,t,cyc); after=sequence(b,np.array(durations),cyc)
    if min(before['tracked_pair_fraction'] or 0,after['tracked_pair_fraction'] or 0)<.8: raise ValueError('low LK coverage; cannot automatically judge')
    p,q=before['acceleration_p95'],after['acceleration_p95']
    if p is None or q is None or q>p+max(.01,.05*p): raise ValueError('LK acceleration regression')
    return durations, {'max_pixel_delta_before':max(oldsteps),'max_pixel_delta_after':max(newsteps),'max_pixel_delta_reduction_percent':100*(1-max(newsteps)/max(oldsteps)), 'opencv_before':before,'opencv_after':after,'artistic_quality':None,'status':'candidate_requires_visual_review'}


def checkout(repo,revision,weights):
    repo=Path(repo).resolve(); weights=Path(weights).resolve()
    if len(revision)!=40 or any(c not in '0123456789abcdef' for c in revision): raise ValueError('exact upstream commit SHA required')
    if not (repo/'inference_img.py').is_file() or not weights.is_dir() or not any(weights.glob('*.pkl')): raise ValueError('actual upstream checkout and trusted trained weights required')
    def git(*args): return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    if git('rev-parse','HEAD')!=revision or git('status','--porcelain','--untracked-files=no'): raise ValueError('checkout revision mismatch or tracked modifications')
    return repo,weights


def run(src,out,mode,factor,repo,revision,weights):
    src,out=Path(src).resolve(),Path(out).resolve()
    if out.exists() or src==out or out.suffix.lower() not in ('.png','.apng'): raise ValueError('new APNG path required')
    fs,t=source(src,mode,factor); repo,weights=checkout(repo,revision,weights)
    n=len(fs); cyc=mode=='loop'; segments=n if cyc else n-1; cand=[]
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        root=Path(tmp); env=os.environ.copy(); env['CUDA_VISIBLE_DEVICES']=''; env['OMP_NUM_THREADS']='2'; env['MKL_NUM_THREADS']='2'
        for i in range(segments):
            work=root/f'{i:04d}'; work.mkdir(); j=(i+1)%n
            for name,f in [('a.png',fs[i]),('b.png',fs[j])]: Image.fromarray(f[:,:,:3]).save(work/name)
            # Official inference_img.py supports --exp 1/2 (factor 2/4) and --model.
            result=subprocess.run([sys.executable,str(repo/'inference_img.py'),'--img',str(work/'a.png'),str(work/'b.png'),'--exp',str(1 if factor==2 else 2),'--model',str(weights)],cwd=work,env=env,capture_output=True,text=True,timeout=180,check=True)
            files=work/'output'
            if {p.name for p in files.glob('*.png')}!={f'img{k}.png' for k in range(factor+1)}: raise ValueError('unexpected upstream output count')
            cand.append(fs[i]) # keep exact original, never re-encode original through network
            for k in range(1,factor):
                with Image.open(files/f'img{k}.png') as im:
                    if im.mode!='RGB' or im.size!=(fs[0].shape[1],fs[0].shape[0]): raise ValueError('unexpected upstream frame format')
                    cand.append(np.array(im.convert('RGBA')))
        if not cyc: cand.append(fs[-1])
        durations,info=assess(fs,t,cand,mode,factor)
        ims=[Image.fromarray(f) for f in cand]; p=root/'candidate.png'
        ims[0].save(p,format='PNG',save_all=True,append_images=ims[1:],duration=durations,loop=0 if cyc else 1,disposal=0,blend=0)
        got,dt,lp=load(p)
        if len(got)!=len(cand) or any(not np.array_equal(a,b) for a,b in zip(got,cand)) or not np.array_equal(dt,durations) or dt.sum()!=t.sum() or lp!=(0 if cyc else 1): raise ValueError('APNG round-trip failed')
        p.replace(out)
    return dict(info,output=str(out),rife_commit=revision,frames_before=n,frames_after=len(cand),duration_ms=int(t.sum()))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('source'); p.add_argument('output'); p.add_argument('--mode',choices=['loop','once'],required=True); p.add_argument('--factor',type=int,choices=[2,4],default=2); p.add_argument('--repo',required=True); p.add_argument('--revision',required=True); p.add_argument('--weights',required=True); p.add_argument('--confirm-opaque-nonorganic-effect',action='store_true',required=True)
    a=p.parse_args(); print(json.dumps(run(a.source,a.output,a.mode,a.factor,a.repo,a.revision,a.weights),indent=2,allow_nan=False))
