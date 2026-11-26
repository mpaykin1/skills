"""Convert authorized FreeMoCap MediaPipe body NPY to calibrated control targets. No synthetic capture."""
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def require(v,msg):
    if not v: raise ValueError(msg)
def prepare(path,cfg):
    require(cfg['rights_confirmed'] is True and cfg['source_sha256']==sha(path),'source approval/hash required')
    require(cfg['tracker']=='mediapipe','only named MediaPipe body landmarks supported')
    require(path.stat().st_size<=128*1024*1024,'capture too large')
    a=np.load(path,allow_pickle=False,mmap_mode='r')
    require(a.ndim==3 and a.shape[2]==3 and 12<=a.shape[0]<=18000 and 33<=a.shape[1]<=37 and a.dtype.kind=='f','unexpected body array')
    names=cfg['marker_names']; require(len(names)==a.shape[1] and len(set(names))==len(names),'explicit ordered marker names required')
    required=['left_hip','right_hip','left_shoulder','right_shoulder','left_knee','right_knee','left_ankle','right_ankle','left_elbow','right_elbow','left_wrist','right_wrist','left_heel','right_heel','left_foot_index','right_foot_index']
    require(set(required)<=set(names),'missing body markers')
    start,end=cfg['start'],cfg['end']; require(type(start)==type(end)==int and 0<=start<end<a.shape[0] and 12<=end-start+1<=1800,'invalid clip range')
    fps=float(cfg['fps']); require(math.isfinite(fps) and 10<=fps<=120,'explicit calibrated FPS required')
    scale={'mm':.001,'m':1.0}[cfg['units']]; basis=np.array(cfg['source_to_blender'],float)
    require(basis.shape==(3,3) and np.allclose(basis@basis.T,np.eye(3),atol=1e-5) and np.linalg.det(basis)>.999,'proper orthonormal basis required')
    floor=float(cfg['floor_z_m']); require(math.isfinite(floor),'calibrated floor required')
    x=np.array(a[start:end+1,[names.index(k) for k in required],:],dtype=np.float64)*scale
    gaps=0
    for j in range(x.shape[1]):
        good=np.isfinite(x[:,j]).all(axis=1); bad=np.flatnonzero(~good)
        require(good[0] and good[-1],'unbounded missing endpoint')
        for run in np.split(bad,np.where(np.diff(bad)!=1)[0]+1):
            if len(run):
                require(len(run)<=2,'tracking gap too long; recapture or inspect SkellyForge')
                lo,hi=run[0]-1,run[-1]+1
                for k in run:x[k,j]=x[lo,j]+(x[hi,j]-x[lo,j])*(k-lo)/(hi-lo)
                gaps+=len(run)
    x=x@basis.T; x[:,:,2]-=floor
    markers={k:x[:,i] for i,k in enumerate(required)}
    hip=(markers['left_hip']+markers['right_hip'])/2; shoulders=(markers['left_shoulder']+markers['right_shoulder'])/2
    require(.15<=float(np.median(np.linalg.norm(shoulders-hip,axis=1)))<=1.2,'calibration/body scale invalid')
    origin=hip[0].copy(); origin[2]=0
    for k in markers:markers[k]-=origin
    hip-=origin; shoulders-=origin
    targets={'hip':hip,'shoulders':shoulders,**markers}
    return {'schema':'freemocap-control-targets-v1','hero_id':cfg['hero_id'],'capture_sha256':sha(path),'clip':cfg['clip'],'fps':fps,'axes':'blender-z-up-metres','interpolated_marker_frames':gaps,'frames':[{'frame':i,'time':i/fps,'targets':{k:v[i].tolist() for k,v in targets.items()}} for i in range(len(hip))]}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('body',type=Path);p.add_argument('config',type=Path);p.add_argument('out',type=Path);args=p.parse_args(); data=prepare(args.body,json.loads(args.config.read_text()));
    with args.out.open('x') as f:json.dump(data,f,allow_nan=False)
