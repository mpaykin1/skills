"""OIDN 2.3.3 CPU-only offline denoiser for approved-source, pre-approval renders.
Requires the independently verified official oidnDenoise executable and its libs.
No fallback masquerading as OIDN; never edit an approved sprite or a VDB grid.
"""
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

MAX_PIXELS=2048*2048

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def png(path):
    with Image.open(path) as im:
        require(im.format=='PNG' and im.mode=='RGBA' and im.width*im.height<=MAX_PIXELS,'Expected bounded RGBA PNG')
        return np.array(im)
def lin(x): return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def srgb(x):
    x=np.clip(x,0,1);return np.where(x<=.0031308,x*12.92,1.055*x**(1/2.4)-.055)
def write_pfm(path,a):
    h,w,c=a.shape;require(c==3 and np.isfinite(a).all(),'PFM RGB finite')
    with Path(path).open('wb') as f:
        f.write(f'PF\n{w} {h}\n-1.0\n'.encode());f.write(np.flipud(a).astype('<f4').tobytes())
def read_pfm(path,shape):
    with Path(path).open('rb') as f:
        require(f.readline().strip()==b'PF','OIDN output PFM');w,h=map(int,f.readline().split());scale=float(f.readline());require((h,w,3)==shape and abs(scale)==1,'OIDN output size or scale mismatch');raw=f.read(w*h*12+1)
    require(len(raw)==w*h*12,'OIDN output size mismatch');a=np.flipud(np.frombuffer(raw,'<f4' if scale<0 else '>f4').reshape(shape));require(np.isfinite(a).all(),'OIDN returned nonfinite values');return a

def protected_mask(a,path=None):
    # Preserve silhouette, translucent parts, transparent RGB and 2px border.
    solid=Image.fromarray(np.where(a[...,3]==255,255,0).astype(np.uint8));safe=np.asarray(solid.filter(ImageFilter.MinFilter(5)))==255
    safe[:2,:]=False;safe[-2:,:]=False;safe[:,:2]=False;safe[:,-2:]=False
    if path is not None:
        with Image.open(path) as im:
            require(im.mode=='L' and im.size==(a.shape[1],a.shape[0]),'Protection mask must be aligned grayscale');safe &= np.asarray(im)==0
    return ~safe

def denoise(exe,input_path,output_path,mask,threads,blend,aux=None):
    a=png(input_path);protect=protected_mask(a,mask)
    x=lin(a[...,:3].astype(np.float32)/255);x[a[...,3]==0]=0
    with tempfile.TemporaryDirectory(prefix='oidn-cpu-') as td:
        t=Path(td);write_pfm(t/'input.pfm',x)
        cmd=[str(exe),'--device','cpu','--filter','RT','--ldr',str(t/'input.pfm'),'--output',str(t/'output.pfm'),'--threads',str(threads),'--maxmem','512','--quality','high']
        if aux:
            for name,flag in [('albedo','--alb'),('normal','--nrm')]:
                if name in aux:
                    g=np.load(aux[name],allow_pickle=False);require(g.shape==x.shape and np.isfinite(g).all(),'Guide size or invalid values');lo=-1 if name=='normal' else 0;require(g.min()>=lo and g.max()<=1,'Guide range');write_pfm(t/f'{name}.pfm',g);cmd += [flag,str(t/f'{name}.pfm')]
        subprocess.run(cmd,check=True,timeout=300,capture_output=True,text=True)
        y=read_pfm(t/'output.pfm',x.shape)
    b=a.copy();b[...,:3]=np.rint(srgb(x*(1-blend)+np.clip(y,0,1)*blend)*255).astype(np.uint8);b[protect]=a[protect]
    Image.fromarray(b,'RGBA').save(output_path)

def checked_file(root,item,key='file'):
    path=(root/item[key]).resolve();require(path.is_relative_to(root) and path.is_file(),'Invalid input path');require(sha(path)==item['sha256'],'Input hash mismatch');return path

def run(config,out,exe,exe_sha,threads):
    config=config.resolve();root=config.parent;meta=json.loads(config.read_text());require(meta.get('source_kind')=='unapproved-raytraced-render' and meta.get('color_space')=='srgb' and meta.get('alpha')=='straight','Only new raytraced render candidates, straight sRGB PNG');require(meta.get('asset_id') and isinstance(meta.get('frames'),list) and 1<=len(meta['frames'])<=240,'Invalid frame list');require(not out.exists(),'Output already exists');exe=exe.resolve();require(exe.is_file() and sha(exe)==exe_sha,'Independently verified OIDN executable required');require(1<=threads<=32,'Thread limit');blend=float(meta.get('blend',.5));require(0<blend<=.7,'Blend must be 0..0.7');require(1<=float(meta['fps'])<=60,'FPS');require([f['frame'] for f in meta['frames']]==list(range(meta['frames'][0]['frame'],meta['frames'][0]['frame']+len(meta['frames']))),'Frame sequence');out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.oidn-stage-',dir=out.parent) as td:
        stage=Path(td)/'result';stage.mkdir();records=[];shape=None
        for f in meta['frames']:
            p=checked_file(root,f);a=png(p);require(shape is None or a.shape==shape,'Frame dimensions changed');shape=a.shape
            mask=checked_file(root,f['protect']) if f.get('protect') else None
            guides={k:checked_file(root,v) for k,v in f.get('guides',{}).items()};require(set(guides)<= {'albedo','normal'},'Unknown guide');dst=stage/f"frame-{f['frame']:06d}.png";denoise(exe,p,dst,mask,threads,blend,guides);records.append({'frame':f['frame'],'input_sha256':sha(p),'file':dst.name,'sha256':sha(dst)})
        result={'schema':'oidn-cpu-v1','source_config_sha256':sha(config),'asset_id':meta['asset_id'],'fps':meta['fps'],'exe_sha256':exe_sha,'device':'cpu','blend':blend,'frames':records};(stage/'denoise.json').write_text(json.dumps(result,indent=2));stage.rename(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('out',type=Path);p.add_argument('--exe',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--threads',type=int,default=min(8,os.cpu_count() or 1));a=p.parse_args();run(a.config,a.out,a.exe,a.sha256,a.threads)
