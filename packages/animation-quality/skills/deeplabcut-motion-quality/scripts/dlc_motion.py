"""Custom single-creature 2D motion diagnostics. No automatic pose edits."""
import argparse,csv,json,hashlib,os,importlib.metadata,sys
from pathlib import Path
import numpy as np
from scipy.stats import median_abs_deviation
import cv2

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def read_csv(path,parts,n,w,h):
    with open(path,newline='',encoding='utf-8-sig') as f: rows=list(csv.reader(f))
    if len(rows)!=n+3 or [r[0] for r in rows[:3]]!=['scorer','bodyparts','coords']:raise ValueError('single-animal DLC CSV with exact frame count required')
    keys=list(zip(rows[1][1:],rows[2][1:])); expected={(p,c) for p in parts for c in ('x','y','likelihood')}
    if set(keys)!=expected or len(keys)!=len(expected) or len(set(rows[0][1:]))!=1 or any(len(r)!=len(keys)+1 for r in rows):raise ValueError('unexpected/duplicate landmarks or scorer')
    if [int(r[0]) for r in rows[3:]]!=list(range(n)):raise ValueError('nonconsecutive frames')
    data=np.array([[float(v) if v.strip() else np.nan for v in r[1:]] for r in rows[3:]],float)
    a=np.stack([data[:,[keys.index((p,c)) for c in ('x','y','likelihood')]] for p in parts],axis=1)
    valid=np.isfinite(a).all(axis=2)&(a[:,:,0]>=0)&(a[:,:,0]<w)&(a[:,:,1]>=0)&(a[:,:,1]<h)&(a[:,:,2]>=.8)&(a[:,:,2]<=1)
    return np.where(valid[:,:,None],a[:,:,:2],np.nan),rows[0][1]

def accel(x,fps,loop):
    if loop:x=np.concatenate([x[-1:],x,x[:1]],axis=0)
    return np.diff(x,n=2,axis=0)*fps**2

def metric(a,b,fps,loop):
    va=np.isfinite(a);vb=np.isfinite(b);both=va&vb
    if np.any(va&~vb) or both.mean()<.9:return {'status':'insufficient_or_regressed_detection','coverage':float(both.mean())}
    aa=accel(np.where(both,a,np.nan),fps,loop);bb=accel(np.where(both,b,np.nan),fps,loop);m=np.isfinite(aa)&np.isfinite(bb)
    if m.sum()<3 or m.mean()<.8:return {'status':'insufficient_acceleration_samples'}
    def stats(z):
        z=z[m];return {'rms':float(np.sqrt(np.mean(z*z))),'p95':float(np.percentile(abs(z),95)),'mad':float(median_abs_deviation(z))}
    x,y=stats(aa),stats(bb)
    return {'status':'proxy_only','coverage':float(both.mean()),'before':x,'after':y,'rms_reduction_pct':None if x['rms']<1e-6 else 100*(1-y['rms']/x['rms']),'max_value_change':float(np.max(abs(a[both]-b[both])))}

def angle(p,ids):
    a,b,c=ids;u=p[:,a]-p[:,b];v=p[:,c]-p[:,b];d=np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1);out=np.full(len(p),np.nan);m=np.isfinite(d)&(d>1e-6);out[m]=np.degrees(np.arccos(np.clip(np.sum(u[m]*v[m],axis=1)/d[m],-1,1)));return out

def compare(p,q,parts,joints,fps,loop):
    if p.shape!=q.shape or len(p)<5:raise ValueError('matched samples required')
    return {name:metric(angle(p,[parts.index(x) for x in triplet]),angle(q,[parts.index(x) for x in triplet]),fps,loop) for name,triplet in joints.items()}

def video_info(path):
    cap=cv2.VideoCapture(str(path));fps=float(cap.get(cv2.CAP_PROP_FPS)); frames=[]
    try:
        if not np.isfinite(fps) or not 1<=fps<=120:raise ValueError('invalid FPS')
        while True:
            ok,f=cap.read()
            if not ok:break
            if len(frames)>=600:raise ValueError('600 frames maximum')
            if frames and f.shape!=frames[0].shape:raise ValueError('variable frame size')
            frames.append(f)
            if len(frames)*f.size>240_000_000:raise ValueError('pixel budget exceeded')
    finally:cap.release()
    if len(frames)<5:raise ValueError('too few frames')
    return frames,fps

def flow_consistency(frames,points,loop):
    # LK independent local check: no correction, no cross-view comparison.
    errs=[];attempt=0
    for i in range(len(frames) if loop else len(frames)-1):
        j=(i+1)%len(frames);m=np.isfinite(points[i]).all(1)&np.isfinite(points[j]).all(1)
        if not m.any():continue
        x=points[i,m].astype(np.float32).reshape(-1,1,2);attempt+=len(x)
        a=cv2.cvtColor(frames[i],cv2.COLOR_BGR2GRAY);b=cv2.cvtColor(frames[j],cv2.COLOR_BGR2GRAY)
        y,s,_=cv2.calcOpticalFlowPyrLK(a,b,x,None)
        if y is None:continue
        z,t,_=cv2.calcOpticalFlowPyrLK(b,a,y,None)
        if z is None:continue
        valid=(s.ravel()==1)&(t.ravel()==1)&(np.linalg.norm(z.reshape(-1,2)-x.reshape(-1,2),axis=1)<=1.5)
        e=np.linalg.norm(y.reshape(-1,2)-points[j,m],axis=1);errs.extend(e[valid&np.isfinite(e)].tolist())
    return {'attempted':attempt,'matched':len(errs),'coverage':len(errs)/attempt if attempt else 0,'p95_disagreement_px':float(np.percentile(errs,95)) if errs else None}

def run(args):
    # trusted local checkpoint and config are mandatory; no downloads in this bridge.
    if importlib.metadata.version('deeplabcut')!='3.0.1':raise ValueError('use isolated DeepLabCut 3.0.1')
    os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['HF_HUB_OFFLINE']='1'
    import deeplabcut
    dest=Path(args.dest).resolve();dest.mkdir(parents=True,exist_ok=False)
    video=Path(args.video).resolve();config=Path(args.config).resolve();frames,fps=video_info(video)
    digest=sha(video)
    deeplabcut.analyze_videos(str(config),[str(video)],shuffle=args.shuffle,save_as_csv=True,destfolder=str(dest),engine=deeplabcut.Engine.PYTORCH,device='cpu')
    files=list(dest.glob('*.csv'))
    if len(files)!=1 or sha(video)!=digest:raise ValueError('ambiguous CSV or changed source')
    meta={'video_sha256':digest,'csv_sha256':sha(files[0]),'frames':len(frames),'fps':fps,'config_sha256':sha(config),'shuffle':args.shuffle,'backend':'deeplabcut-3.0.1-pytorch-cpu'}
    (dest/'capture.json').write_text(json.dumps(meta,indent=2))

def main():
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='cmd',required=True)
    r=sub.add_parser('capture');r.add_argument('config');r.add_argument('video');r.add_argument('dest');r.add_argument('--shuffle',type=int,default=1);r.add_argument('--confirm-trusted-trained-single-creature-project',action='store_true',required=True)
    c=sub.add_parser('compare');c.add_argument('before');c.add_argument('after');c.add_argument('before_csv');c.add_argument('after_csv');c.add_argument('before_manifest');c.add_argument('after_manifest');c.add_argument('schema');c.add_argument('--mode',choices=['once','loop'],required=True);c.add_argument('--confirm-same-creature-camera-cfr-timeline-model',action='store_true',required=True)
    a=ap.parse_args()
    if a.cmd=='capture':run(a);return
    spec=json.loads(Path(a.schema).read_text());parts=spec['parts'];joints=spec['joints']
    if len(parts)!=len(set(parts)) or not joints or any(len(x)!=3 or len(set(x))!=3 or not set(x)<=set(parts) for x in joints.values()):raise ValueError('explicit valid joint schema required')
    f,fps=video_info(a.before);g,fps2=video_info(a.after)
    if len(f)!=len(g) or f[0].shape!=g[0].shape or abs(fps-fps2)>1e-6:raise ValueError('matched CFR clips required')
    h,w=f[0].shape[:2];p,s=read_csv(a.before_csv,parts,len(f),w,h);q,t=read_csv(a.after_csv,parts,len(g),w,h)
    if s!=t:raise ValueError('same scorer required')
    metas=[]
    for video,tracks,manifest in [(a.before,a.before_csv,a.before_manifest),(a.after,a.after_csv,a.after_manifest)]:
        m=json.loads(Path(manifest).read_text());metas.append(m)
        if m['video_sha256']!=sha(video) or m['csv_sha256']!=sha(tracks) or m['frames']!=len(f) or abs(m['fps']-fps)>1e-6:raise ValueError('capture provenance mismatch')
    if any(metas[0].get(k)!=metas[1].get(k) for k in ('config_sha256','shuffle','backend')):raise ValueError('model provenance mismatch')
    loop=a.mode=='loop';print(json.dumps({'joint_metrics':compare(p,q,parts,joints,fps,loop),'opencv_before':flow_consistency(f,p,loop),'opencv_after':flow_consistency(g,q,loop),'approval':False,'artistic_quality_percent':None},allow_nan=False))
if __name__=='__main__':main()
