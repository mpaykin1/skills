import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image

def require(ok,msg):
    if not ok:raise ValueError(msg)
def audit(root):
    m=json.loads((root/'ao.json').read_text());require(m['schema']=='meta-embree-static-ao-v1' and all(re.fullmatch('[a-f0-9]{64}',m[k]) for k in ('source_sha256','native_sha256')) and 8<=m['samples']<=128,'manifest')
    w,h=m['size'];require(1<=w<=512 and 1<=h<=512,'size')
    a={}
    for k in ('ao.png','visibility.png','mask.png'):
        p=root/k;require(hashlib.sha256(p.read_bytes()).hexdigest()==m['maps'][k],'hash');im=Image.open(p);require(im.mode=='L' and im.size==(w,h),'format');a[k]=np.asarray(im)
    mask=a['mask.png'];require(np.isin(mask,[0,255]).all() and mask.any(),'mask');require(np.all(a['ao.png'][mask==0]==255) and np.all(a['visibility.png'][mask==0]==255) and np.isin(a['visibility.png'],[0,255]).all(),'values');return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pack',type=Path);audit(p.parse_args().pack)
