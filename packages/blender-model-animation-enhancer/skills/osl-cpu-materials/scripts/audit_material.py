import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image

def require(ok,msg):
    if not ok: raise ValueError(msg)
def audit(root):
    m=json.loads((root/'material.json').read_text());n=m['size'];require(m['schema']=='meta-osl-pbr-v1' and m['preset'] in ('cloth','steel') and n in (256,512,1024,2048) and all(re.fullmatch('[0-9a-f]{64}',m[k]) for k in ('source_recipe_sha256','shader_sha256')),'manifest');a={}
    for key in ('baseColor','normal','orm','height'):
        f=root/(key+'.png');e=m['maps'][key];require(e['file']==f.name and hashlib.sha256(f.read_bytes()).hexdigest()==e['sha256'],'hash');require(e['color_space']==('srgb' if key=='baseColor' else 'linear'),'color space');im=Image.open(f);require(im.size==(n,n) and im.mode==('L' if key=='height' else 'RGB'),'image format');a[key]=np.asarray(im,dtype=np.float32)/255
    require(float(a['baseColor'].std(axis=(0,1)).max())>.001,'flat base color');require(float(a['height'].std())>.001,'flat height');v=2*a['normal']-1;require(np.max(np.abs(np.linalg.norm(v,axis=-1)-1))<.015 and v[...,2].min()>0,'invalid normal');require(np.all(a['orm'][...,0]==1) and np.all(a['orm'][...,2]==int(m['preset']=='steel')),'ORM channels');require(a['orm'][...,1].min()>=.1 and a['orm'][...,1].max()<=.96,'roughness');return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pack',type=Path);audit(p.parse_args().pack)
