"""Pack linear OSL renders to glTF-ready PBR textures, no denoising of maps."""
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
from PIL import Image

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def pack(src,out,strength):
    m=json.loads((src/'linear.json').read_text());n=m['size'];require(m['schema']=='meta-osl-linear-v1' and m['backend']=='cycles-cpu-osl' and m['preset'] in ('cloth','steel') and n in (256,512,1024,2048) and math.isfinite(strength) and 0<strength<=1,'metadata');require(not out.exists(),'output exists');data={}
    for name in ['Albedo','Roughness','Height']:
        p=src/(name+'.npy');require(m['maps'][name]['file']==p.name and sha(p)==m['maps'][name]['sha256'],'source hash');v=np.load(p,allow_pickle=False);require(v.shape==(n,n,3) and v.dtype==np.float32 and np.isfinite(v).all() and v.min()>=0 and v.max()<=1,'linear map');require(float(v.std(axis=(0,1)).max())>1e-5,'flat map');data[name]=v
    for name in ['Roughness','Height']:require(np.max(np.abs(data[name]-data[name][...,:1]))<1e-4,'non-scalar map')
    out.mkdir(parents=True);al=data['Albedo'];srgb=np.where(al<=.0031308,12.92*al,1.055*al**(1/2.4)-.055);rough=data['Roughness'][...,0];height=data['Height'][...,0];dy,dx=np.gradient(height);normal=np.stack((-dx*n*strength,dy*n*strength,np.ones_like(height)),axis=-1);normal/=np.linalg.norm(normal,axis=-1,keepdims=True);orm=np.stack((np.ones_like(rough),rough,np.full_like(rough,1. if m['preset']=='steel' else 0.)),axis=-1)
    maps={'baseColor':srgb,'normal':normal*.5+.5,'orm':orm,'height':height};files={}
    for key,val in maps.items():
        p=out/(key+'.png');Image.fromarray(np.rint(np.clip(val,0,1)*255).astype(np.uint8)).save(p);files[key]={'file':p.name,'sha256':sha(p),'color_space':'srgb' if key=='baseColor' else 'linear'}
    meta={'schema':'meta-osl-pbr-v1','preset':m['preset'],'size':n,'source_recipe_sha256':sha(src/'linear.json'),'shader_sha256':m['shader_sha256'],'normal_strength':strength,'maps':files,'approved':False,'tileable':False};(out/'material.json').write_text(json.dumps(meta,indent=2));return meta
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path);p.add_argument('--strength',type=float,default=.12);a=p.parse_args();pack(a.source,a.out,a.strength)
