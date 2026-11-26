"""MediaPipe CPU humanoid pose diagnostics; no pose generation or automatic retarget."""
import argparse, hashlib, json, importlib.metadata
from pathlib import Path
import numpy as np
from scipy.stats import median_abs_deviation

JOINTS={'elbow.L':(11,13,15),'elbow.R':(12,14,16),'knee.L':(23,25,27),'knee.R':(24,26,28),'hip.L':(11,23,25),'hip.R':(12,24,26),'shoulder.L':(23,11,13),'shoulder.R':(24,12,14)}
# 2-D projection angles only. Never infer actual bone lengths/angles or foot contact.
def angles(points, confidence, min_conf=.75):
    p=np.asarray(points,float); c=np.asarray(confidence,float)
    if p.ndim!=3 or p.shape[1:]!=(33,2) or c.shape!=p.shape[:2]: raise ValueError('expected Nx33x2 and Nx33 confidence')
    out={}
    for key,(a,b,d) in JOINTS.items():
        u,v=p[:,a]-p[:,b],p[:,d]-p[:,b]; den=np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1)
        valid=(c[:,[a,b,d]].min(axis=1)>=min_conf)&np.isfinite(u).all(axis=1)&np.isfinite(v).all(axis=1)&(den>1e-6)
        val=np.full(len(p),np.nan); val[valid]=np.degrees(np.arccos(np.clip((u[valid]*v[valid]).sum(axis=1)/den[valid],-1,1)));out[key]=val
    return out

def angular_acceleration(a,t,loop=False,period=None):
    a=np.asarray(a,float);t=np.asarray(t,float)
    if len(a)!=len(t) or len(t)<5 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):raise ValueError('invalid timeline')
    if loop:
        if period is None or period<=t[-1]-t[0]:raise ValueError('invalid period')
        a=np.r_[a[-1],a,a[0]];t=np.r_[t[-1]-period,t,t[0]+period]
    d=np.diff(t);v=np.diff(a)/d; return np.diff(v)/((d[:-1]+d[1:])*.5)

def compare_series(before,after,t,loop=False,period=None):
    result={}
    for joint in JOINTS:
        x,y=before[joint],after[joint]; bx=np.isfinite(x);by=np.isfinite(y)
        common=bx&by
        # Refuse confidence loss and insufficient matched support; never interpolate missed poses.
        if np.any(bx&~by) or common.mean()<.9:
            result[joint]={'status':'insufficient_or_regressed_detection','coverage':float(common.mean())};continue
        xx=np.where(common,x,np.nan);yy=np.where(common,y,np.nan)
        a=angular_acceleration(xx,t,loop,period);b=angular_acceleration(yy,t,loop,period)
        valid=np.isfinite(a)&np.isfinite(b)
        if valid.sum()<3 or valid.mean()<.8:
            result[joint]={'status':'insufficient_matched_samples'};continue
        def stats(z):
            z=z[valid]; return {'rms_deg_s2':float(np.sqrt(np.mean(z*z))),'p95_abs_deg_s2':float(np.percentile(abs(z),95)), 'mad_deg_s2':float(median_abs_deviation(z,scale=1))}
        old,new=stats(a),stats(b);o=old['rms_deg_s2'];n=new['rms_deg_s2']
        result[joint]={'status':'measured_proxy_only','matched_acceleration_samples':int(valid.sum()),'coverage':float(common.mean()),'before':old,'after':new,'rms_reduction_pct':None if o<1e-6 else 100*(o-n)/o,'max_projected_angle_change_deg':float(np.max(abs(x[common]-y[common])))}
    return result

def capture(frames,model,expected_sha,bg):
    import mediapipe as mp
    if importlib.metadata.version('mediapipe')!='0.10.32': raise ValueError('use pinned MediaPipe 0.10.32')
    if len(expected_sha)!=64 or hashlib.sha256(Path(model).read_bytes()).hexdigest()!=expected_sha.lower():raise ValueError('unverified model SHA256')
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    opts=vision.PoseLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(model),delegate=python.BaseOptions.Delegate.CPU),running_mode=vision.RunningMode.IMAGE,num_poses=2,min_pose_detection_confidence=.75,min_pose_presence_confidence=.75)
    p=np.full((len(frames),33,2),np.nan);c=np.zeros((len(frames),33));counts=[]
    with vision.PoseLandmarker.create_from_options(opts) as detector:
        for i,f in enumerate(frames):
            h,w=f.shape[:2];alpha=f[:,:,3:4].astype(np.float32)/255
            rgb=np.ascontiguousarray(np.rint(f[:,:,:3]*alpha+bg*(1-alpha)).astype(np.uint8))
            r=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb)); counts.append(len(r.pose_landmarks))
            if len(r.pose_landmarks)!=1 or len(r.pose_landmarks[0])!=33:continue
            for j,l in enumerate(r.pose_landmarks[0]):
                if l.visibility is None or l.presence is None:continue
                p[i,j]=(l.x*w,l.y*h);c[i,j]=min(l.visibility,l.presence)
                if not (np.isfinite(p[i,j]).all() and 0<=l.x<=1 and 0<=l.y<=1 and np.isfinite(c[i,j])):c[i,j]=0;p[i,j]=np.nan
    return angles(p,c),counts

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('before',type=Path);ap.add_argument('after',type=Path);ap.add_argument('--model',type=Path,required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--mode',choices=['once','loop'],required=True);ap.add_argument('--confirm-single-humanoid-same-camera-same-timeline',action='store_true',required=True);ap.add_argument('--background',type=int,choices=[32,224],required=True);args=ap.parse_args()
    import quality
    f,t,l=quality.load(args.before);g,u,m=quality.load(args.after)
    if not 5<=len(f)<=600 or len(f)!=len(g) or f[0].shape!=g[0].shape or not np.array_equal(t,u) or l!=m or not np.all(np.isfinite(t)&(t>0)):raise ValueError('same camera, canvas, frame count, durations and loop required')
    if (args.mode=='loop')!=(l==0):raise ValueError('loop metadata and mode mismatch')
    if sum(x.size for x in f+g)>320_000_000:raise ValueError('decoded pixel budget exceeded')
    # Independent image inference avoids temporal tracking masking frame jitter.
    a,ac=capture(f,args.model,args.sha256,args.background);b,bc=capture(g,args.model,args.sha256,args.background)
    if any(x>1 for x in ac+bc):raise ValueError('multiple poses detected; no identity matching')
    ts=np.r_[0,np.cumsum(t[:-1])]/1000;period=float(t.sum()/1000)
    result=compare_series(a,b,ts,args.mode=='loop',period)
    audit1=quality.audit(args.before,args.mode,True);audit2=quality.audit(args.after,args.mode,True)
    print(json.dumps({'joint_metrics':result,'single_detection_frames':[ac.count(1),bc.count(1)],'opencv_before':audit1,'opencv_after':audit2,'artistic_quality_percent':None,'approval':False,'interpretation':'2D projected angular acceleration only; requires visual review of identity, intended timing, support and pose. No retarget or correction performed.'},allow_nan=False))
if __name__=='__main__':main()
