"""CPU motion diagnostics and exact rigid constant-speed timing correction."""
import cv2, numpy as np, math, tempfile
from pathlib import Path
from PIL import Image

def analyze(a,b,dt):
    # Inputs are reduced premultiplied RGBA in 0..1. Measure only textured visible points.
    def gray(x): return np.uint8(np.clip((cv2.cvtColor(x[:,:,:3],cv2.COLOR_RGB2GRAY)*.8+x[:,:,3]*.2)*255,0,255))
    x,y=gray(a),gray(b)
    if min(x.shape)<12 or dt<=0: return None
    mask=np.uint8(a[:,:,3]>.15)*255
    p=cv2.goodFeaturesToTrack(x, maxCorners=300, qualityLevel=.01,minDistance=4,mask=mask,blockSize=3)
    if p is None or len(p)<6: return None
    opts=dict(winSize=(21,21),maxLevel=3,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.01))
    q,s,_=cv2.calcOpticalFlowPyrLK(x,y,p,None,**opts)
    if q is None or s is None: return None
    r,t,_=cv2.calcOpticalFlowPyrLK(y,x,q,None,**opts)
    if r is None or t is None: return None
    pp,qq,rr=p[:,0],q[:,0],r[:,0]; fb=np.linalg.norm(pp-rr,axis=1)
    ok=(s.ravel()==1)&(t.ravel()==1)&np.isfinite(fb)&(fb<=1.)&np.isfinite(qq).all(axis=1)
    ok &= (qq[:,0]>=0)&(qq[:,0]<x.shape[1]-1)&(qq[:,1]>=0)&(qq[:,1]<x.shape[0]-1)
    if ok.any():
        idx=np.where(ok)[0]; pos=np.rint(qq[idx]).astype(int); ok[idx]&=b[pos[:,1],pos[:,0],3]>.15
    coverage=float(ok.mean())
    if ok.sum()<6 or coverage<.4: return dict(track_count=int(ok.sum()),candidate_count=len(p),coverage=coverage,velocity=None)
    d=qq[ok]-pp[ok]; scale=math.hypot(*x.shape); v=d/scale/(dt/1000.)
    med=np.median(v,axis=0)
    return dict(track_count=int(ok.sum()),candidate_count=len(p),coverage=coverage,fb_error_px_p95=float(np.percentile(fb[ok],95)),velocity=med.tolist(),speed_p90=float(np.percentile(np.linalg.norm(v,axis=1),90)),motion_dispersion=float(np.median(np.linalg.norm(v-med,axis=1))))

def sequence(frames,t,cyc):
    ids=list(zip(range(len(frames)-1),range(1,len(frames))))
    if cyc and len(frames)>1: ids.append((len(frames)-1,0))
    pairs=[]
    for i,j in ids:
        p=analyze(frames[i],frames[j],t[i]); pairs.append(dict(start=i,end=j,**(p or {'velocity':None,'coverage':0.})))
    accel=[]
    for i,j in list(zip(range(len(pairs)-1),range(1,len(pairs))))+([(len(pairs)-1,0)] if cyc and len(pairs)>1 else []):
        a,b=pairs[i],pairs[j]
        if a['velocity'] is not None and b['velocity'] is not None:
            dt=(t[a['start']]+t[b['start']])/2000
            accel.append({'at_frame':b['start'],'acceleration':float(np.linalg.norm(np.array(b['velocity'])-a['velocity'])/dt)})
    values=[x['acceleration'] for x in accel]; median=float(np.median(values)) if values else None
    outliers=[x for x in accel if median is not None and x['acceleration']>max(.5,4*median)]
    return dict(opencv_version=cv2.__version__,pairs=pairs,tracked_pair_fraction=sum(p['velocity'] is not None for p in pairs)/len(pairs) if pairs else None,acceleration_p95=float(np.percentile(values,95)) if values else None,acceleration_outliers=outliers,seam=pairs[-1] if cyc and pairs else None,artistic_quality=None)

def translation_positions(fs):
    # Exact crop equality protects every visible RGBA pixel, rejects morph/rotation/occlusion.
    boxes=[cv2.boundingRect(np.uint8(f[:,:,3]>0)) for f in fs]
    if any(w==0 or h==0 for x,y,w,h in boxes): raise ValueError('empty sprite')
    x,y,w,h=boxes[0]; ref=fs[0][y:y+h,x:x+w]
    for f,(u,v,ww,hh) in zip(fs,boxes):
        if (ww,hh)!=(w,h) or not np.array_equal(ref,f[v:v+hh,u:u+ww]): raise ValueError('not exact rigid translation; use authored motion')
        if u==0 or v==0 or u+ww==f.shape[1] or v+hh==f.shape[0]: raise ValueError('possible clipping')
    return np.array([(x,y) for x,y,w,h in boxes],float)

def constant_speed_repair(src,dst):
    from quality import load
    src,dst=Path(src),Path(dst)
    if dst.exists() or src.resolve()==dst.resolve() or dst.suffix.lower() not in ('.png','.apng'): raise ValueError('new APNG path required')
    fs,t,loop=load(src)
    if len(fs)<4 or not np.all(t>0) or not np.allclose(t,np.round(t)): raise ValueError('need >=4 frames and valid integer durations')
    with Image.open(src) as im:
        if loop is not None and not (im.format=='PNG' and loop==1): raise ValueError('only one-shot clips')
    pos=translation_positions(fs); d=np.diff(pos,axis=0); dist=np.linalg.norm(d,axis=1)
    if np.any(dist<=0): raise ValueError('holds need authored timing')
    direction=d[0]/dist[0]
    if not np.allclose(d/dist[:,None],direction,atol=.015): raise ValueError('not straight constant-direction travel')
    travel=int(sum(t[:-1])); ideal=travel*dist/dist.sum(); cum=np.rint(np.r_[0,np.cumsum(ideal)]).astype(int); durations=np.r_[np.diff(cum),int(t[-1])]
    if min(durations)<10: raise ValueError('unsafe short duration')
    def cv(times):
        speed=dist/(times[:-1]/1000); return float(speed.std()/speed.mean())
    before,after=cv(t),cv(durations)
    if before-after<.005: raise ValueError('no meaningful velocity uniformity gain')
    dst.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dst.parent) as tmp:
        p=Path(tmp)/'out.png'; ims=[Image.fromarray(f) for f in fs]
        ims[0].save(p,format='PNG',save_all=True,append_images=ims[1:],duration=durations.tolist(),loop=1,disposal=0,blend=0)
        new,dt,nloop=load(p)
        if len(new)!=len(fs) or any(not np.array_equal(a,b) for a,b in zip(fs,new)) or not np.array_equal(dt,durations) or sum(dt)!=sum(t) or nloop!=1: raise ValueError('pixel/timeline verification failed')
        p.replace(dst)
    return dict(output=str(dst),speed_cv_before=before,speed_cv_after=after,relative_speed_cv_reduction_percent=100*(before-after)/before,artistic_quality=None,frame_count=len(fs),duration_ms=int(sum(t)))
