"""CPU animation diagnostics; conservative timing-only repair. No artistic claims."""
import argparse, json, math, hashlib, tempfile
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import opencv_motion

EXT={'.gif','.apng','.webp','.png'}
def load(p):
    frames=[]; times=[]
    with Image.open(p) as im:
        loop=im.info.get('loop',None); default=bool(im.info.get('default_image',False))
        for i in range(int(default),getattr(im,'n_frames',1)):
            im.seek(i); f=np.array(im.convert('RGBA')); f[f[:,:,3]==0,:3]=0
            frames.append(f); times.append(float(im.info.get('duration',0) or 0))
    if not frames: raise ValueError('no frames')
    return frames,np.array(times),loop

def digest(a): return hashlib.sha256(a.tobytes()).hexdigest()
def reduced(a):
    h,w=a.shape[:2]; k=min(1,192/max(h,w)); f=a.astype(np.float32)/255
    f[:,:,:3]*=f[:,:,3:4]
    return cv2.resize(f,(max(1,round(w*k)),max(1,round(h*k))),interpolation=cv2.INTER_AREA)
def delta(a,b):
    mask=(a[:,:,3]>.02)|(b[:,:,3]>.02)
    return float(np.abs(a-b)[mask].mean()) if mask.any() else 0.
def pairflow(a,b):
    def gray(f): return np.uint8(np.clip(cv2.cvtColor(f[:,:,:3],cv2.COLOR_RGB2GRAY)*.8+f[:,:,3]*.2,0,1)*255)
    x,y=gray(a),gray(b); mask=a[:,:,3]>.1
    if min(x.shape)<12 or not mask.any(): return None
    f=cv2.calcOpticalFlowFarneback(x,y,None,.5,3,15,3,5,1.2,0)
    g=cv2.calcOpticalFlowFarneback(y,x,None,.5,3,15,3,5,1.2,0)
    yy,xx=np.indices(x.shape,dtype=np.float32); xx+=f[:,:,0]; yy+=f[:,:,1]
    back=cv2.remap(g,xx,yy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    valid=mask&(xx>=0)&(yy>=0)&(xx<x.shape[1]-1)&(yy<x.shape[0]-1)
    if not valid.any(): return None
    return float(np.median(np.linalg.norm(f[valid]+back[valid],axis=1))/max(x.shape)),float(np.median(np.linalg.norm(f[valid],axis=1))/max(x.shape))
def audit(p,mode='auto',flow=False):
    fs,t,loop=load(p); n=len(fs); hashes=[digest(f) for f in fs]; cyc=(loop==0) if mode=='auto' else mode=='loop'
    a=[reduced(f) for f in fs]; dif=[delta(x,y) for x,y in zip(a,a[1:])]
    seam=delta(a[-1],a[0]) if cyc and n>1 else None
    valid=bool(np.all(t>0)); typical=float(np.median(dif)) if dif else 0
    bounds=[np.where(f[:,:,3]>0) for f in fs]; empty=sum(not len(y) for y,x in bounds)
    areas=np.array([len(y) for y,x in bounds]); centers=[(float(np.mean(x)),float(np.mean(y))) if len(y) else None for y,x in bounds]
    diag=math.hypot(*fs[0].shape[:2]); ids=list(zip(range(n-1),range(1,n)))+([(n-1,0)] if cyc and n>1 else [])
    speeds=[]
    for i,j in ids:
        if centers[i] is not None and centers[j] is not None and t[i]>0: speeds.append(np.array(centers[j])-centers[i]); speeds[-1]=speeds[-1]/diag/(t[i]/1000)
        else: speeds.append(None)
    acc=[float(np.linalg.norm(y-x)) for x,y in zip(speeds,speeds[1:]) if x is not None and y is not None]
    if cyc and len(speeds)>1 and speeds[0] is not None and speeds[-1] is not None: acc.append(float(np.linalg.norm(speeds[0]-speeds[-1])))
    flows=[v for i,j in ids if (v:=pairflow(a[i],a[j])) is not None] if flow else []
    flags=[]
    if n<2 or len(set(hashes))<2: flags.append('static_or_missing_motion')
    if not valid: flags.append('invalid_or_unknown_timing')
    if empty: flags.append('empty_frames_review')
    if seam is not None and seam>max(.03,3*typical): flags.append('loop_seam_outlier_review')
    if n>1 and max(dif,default=0)>max(.05,4*typical): flags.append('adjacent_jump_review')
    return dict(opencv_motion=opencv_motion.sequence(a,t,cyc) if flow else None,file=str(p),size=[fs[0].shape[1],fs[0].shape[0]],frames=n,unique_frames=len(set(hashes)),adjacent_identical=sum(x==y for x,y in zip(hashes,hashes[1:])),duration_ms=float(sum(t)),fps=n*1000/float(sum(t)) if valid else None,frame_duration_cv=float(t.std()/t.mean()) if valid else None,loop_metadata=loop,loop_checked=cyc,empty_frames=empty,area_cv=float(areas.std()/areas.mean()) if areas.mean() else None,median_adjacent_delta=typical,max_adjacent_delta=max(dif,default=0),seam_delta=seam,centroid_velocity_change_p95=float(np.percentile(acc,95)) if acc else None,flow_fb_error_median=float(np.median([v[0] for v in flows])) if flows else None,flags=flags,artistic_quality=None)

def score(a,profile):
    # Engineering rubric only: explicit uniform timing and loop expectations.
    if profile not in ('uniform-loop','uniform-once'): raise ValueError('explicit uniform profile required')
    if a['unique_frames']<2 or a['fps'] is None or a['empty_frames']: return None
    cv=a['frame_duration_cv']; base=100*max(0,1-cv)
    if profile=='uniform-loop':
        if a['seam_delta'] is None: return None
        ratio=a['seam_delta']/max(.01,a['median_adjacent_delta'])
        return .6*base+40*max(0,1-max(0,ratio-1)/3)
    return base

def compare(before,after,profile):
    x,y=score(before,profile),score(after,profile)
    return {'before':before,'after':after,'technical_index_before':x,'technical_index_after':y,'delta_points':None if x is None or y is None else y-x,'relative_percent':None if x is None or y is None or x<=0 else 100*(y-x)/x,'artistic_quality_percent':None}

def repair(src,dst,profile):
    # Explicitly uniform motions only. Preserve every decoded pose and total duration.
    src,dst=Path(src),Path(dst)
    if src.resolve()==dst.resolve() or dst.exists(): raise ValueError('new output path required')
    if dst.suffix.lower() not in ('.png','.apng'): raise ValueError('use lossless APNG output')
    fs,t,loop=load(src); n=len(fs)
    if n<2 or not np.all(t>0) or not np.allclose(t,np.round(t)): raise ValueError('invalid input timeline')
    if len({digest(f) for f in fs})!=n: raise ValueError('duplicate/held poses require authored timing review')
    if profile=='uniform-loop' and loop!=0: raise ValueError('not an infinite loop')
    if profile=='uniform-once' and loop==0: raise ValueError('not a one-shot')
    with Image.open(src) as im:
        if loop not in (0,None) and not (im.format=='PNG' and loop==1): raise ValueError('finite repeat count requires manual mapping')
    total=int(round(sum(t))); q,r=divmod(total,n)
    if q<1: raise ValueError('invalid output timing')
    durations=[q+((i+1)*r//n-i*r//n) for i in range(n)]
    imgs=[Image.fromarray(f) for f in fs]; dst.parent.mkdir(parents=True,exist_ok=True)
    mode='loop' if profile=='uniform-loop' else 'once'
    with tempfile.TemporaryDirectory(dir=dst.parent) as tmp:
        out=Path(tmp)/'candidate.png'; imgs[0].save(out,format='PNG',save_all=True,append_images=imgs[1:],duration=durations,loop=0 if loop==0 else 1,disposal=0,blend=0)
        new,dt,newloop=load(out)
        if len(new)!=n or any(not np.array_equal(f,g) for f,g in zip(fs,new)) or not np.array_equal(dt,durations) or sum(dt)!=total or newloop!=(0 if loop==0 else 1): raise ValueError('lossless frame/timeline guard failed')
        result=compare(audit(src,mode),audit(out,mode),profile)
        if result['delta_points'] is None or result['delta_points']<=1e-6: raise ValueError('no measurable technical gain')
        result['after']['file']=str(dst); out.replace(dst)
    return result

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('audit'); a.add_argument('path'); a.add_argument('--mode',choices=['auto','loop','once'],default='auto'); a.add_argument('--flow',action='store_true')
    for name in ('compare','repair'):
        a=sub.add_parser(name); a.add_argument('before'); a.add_argument('after'); a.add_argument('--profile',choices=['uniform-loop','uniform-once'],required=True)
    a=sub.add_parser('repair-rigid-travel'); a.add_argument('before'); a.add_argument('after'); a.add_argument('--confirm-constant-speed',action='store_true',required=True)
    x=p.parse_args()
    if x.cmd=='audit':
        root=Path(x.path)
        if root.is_dir():
            result=[]
            for f in sorted(root.rglob('*')):
                if f.is_file() and f.suffix.lower() in EXT:
                    try:
                        with Image.open(f) as im:
                            if getattr(im,'n_frames',1)<2 and f.suffix.lower() not in ('.gif','.apng'): continue
                        result.append(audit(f,x.mode,x.flow))
                    except Exception as e: result.append({'file':str(f),'error':str(e)})
        else: result=audit(root,x.mode,x.flow)
    elif x.cmd=='compare':
        mode='loop' if x.profile=='uniform-loop' else 'once'; result=compare(audit(x.before,mode),audit(x.after,mode),x.profile)
    elif x.cmd=='repair-rigid-travel': result=opencv_motion.constant_speed_repair(x.before,x.after)
    else: result=repair(x.before,x.after,x.profile)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
if __name__=='__main__': main()
