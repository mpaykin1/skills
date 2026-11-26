"""Offline CPU ray-visibility/AO for authored UV position/normal samples. No fallback pretending to be Embree."""
import argparse, hashlib, json, math, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def require(x,msg):
    if not x:raise ValueError(msg)
def bake(src,out,exe,expected,source_hash,light,radius,eps,samples,threads):
    require(not out.exists() and src.is_file() and src.stat().st_size<=128*1024*1024,'input/output')
    require(sha(src)==source_hash and sha(exe)==expected,'hash mismatch')
    require(8<=samples<=128 and 1<=threads<=32 and math.isfinite(radius) and math.isfinite(eps) and 0<eps<radius<=1000 and len(light)==3 and all(map(math.isfinite,light)),'settings')
    # Trusted internally generated NPZ only; reject large expanded input before numpy loads it.
    import zipfile
    with zipfile.ZipFile(src) as z:require(sum(x.file_size for x in z.infolist())<=128*1024*1024,'expanded size')
    with np.load(src,allow_pickle=False) as z:
        v=z['vertices'];t=z['triangles'];p=z['positions'];n=z['normals'];mask=z['mask']
    require(v.ndim==2 and v.shape[1]==3 and 3<=len(v)<=2000000 and np.issubdtype(v.dtype,np.floating) and np.isfinite(v).all(),'vertices')
    require(t.ndim==2 and t.shape[1]==3 and 1<=len(t)<=2000000 and np.issubdtype(t.dtype,np.integer) and t.min()>=0 and t.max()<len(v),'triangles')
    require(p.ndim==3 and p.shape[-1]==3 and p.shape==n.shape and all(1<=k<=512 for k in p.shape[:2]) and mask.shape==p.shape[:2] and mask.dtype==np.bool_,'sample maps')
    pp=p[mask];nn=n[mask];require(1<=len(pp)<=262144 and np.isfinite(pp).all() and np.isfinite(nn).all() and np.max(np.abs(np.linalg.norm(nn,axis=1)-1))<.01,'invalid samples')
    with tempfile.TemporaryDirectory() as tmp:
        f=Path(tmp)/'input.txt';r=Path(tmp)/'output.txt'
        with f.open('w') as w:
            w.write(f'{len(v)} {len(t)} {len(pp)} {samples} {threads} {radius} {eps}\n');w.write(' '.join(map(str,light))+'\n');np.savetxt(w,v,fmt='%.9g');np.savetxt(w,t,fmt='%d');np.savetxt(w,np.hstack((pp,nn)),fmt='%.9g')
        with f.open('rb') as i,r.open('wb') as o:subprocess.run([str(exe.resolve())],stdin=i,stdout=o,check=True,timeout=900)
        result=np.loadtxt(r,ndmin=2);require(result.shape==(len(pp),2) and np.isfinite(result).all() and np.all((result>=0)&(result<=1)) and np.all(np.isin(result[:,1],[0,1])),'native output')
    ao=np.full(mask.shape,255,np.uint8);vis=ao.copy();ao[mask]=np.rint(result[:,0]*255).astype(np.uint8);vis[mask]=np.rint(result[:,1]*255).astype(np.uint8)
    out.mkdir(parents=True);Image.fromarray(ao).save(out/'ao.png');Image.fromarray(vis).save(out/'visibility.png');Image.fromarray(mask.astype(np.uint8)*255).save(out/'mask.png');m={'schema':'meta-embree-static-ao-v1','source_sha256':source_hash,'native_sha256':expected,'size':[int(mask.shape[1]),int(mask.shape[0])],'samples':samples,'radius_m':radius,'epsilon_m':eps,'light_world_m':light,'approved':False,'maps':{k:sha(out/k) for k in ('ao.png','visibility.png','mask.png')}};(out/'ao.json').write_text(json.dumps(m,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('out',type=Path);p.add_argument('--exe',type=Path,required=True);p.add_argument('--exe-sha',required=True);p.add_argument('--source-sha',required=True);p.add_argument('--light',type=float,nargs=3,required=True);p.add_argument('--radius',type=float,default=1);p.add_argument('--epsilon',type=float,default=.001);p.add_argument('--samples',type=int,default=32);p.add_argument('--threads',type=int,default=4);a=p.parse_args();bake(a.input,a.out,a.exe,a.exe_sha,a.source_sha,a.light,a.radius,a.epsilon,a.samples,a.threads)
