"""Audit real packed bytes and the projected atlas; not a visual approval gate."""
import argparse,json,hashlib,math
from pathlib import Path
import numpy as np
from PIL import Image

def check(x,msg):
    if not x: raise ValueError(msg)
def audit(root):
    m=json.loads((root/'volume.json').read_text()); n=m['frames']; w,h,d=m['size'];cols=m['cols'];rows=m['rows'];
    check(m['schema']=='openvdb-fire-v1' and m['source']=='blender-mantaflow-openvdb' and m['fps']==24 and 16<=n<=64 and all(2<=x<=64 for x in (w,h,d)),'schema/dimensions'); check(4*n*w*h*d<=33554432,'memory budget')
    check(len(m['source_frame_sha256'])==n and len(set(m['source_frame_sha256']))>1,'static source cache')
    raw=(root/'volume.rgba').read_bytes();png=(root/'fallback.png').read_bytes();check(hashlib.sha256(raw).hexdigest()==m['sha256'] and hashlib.sha256(png).hexdigest()==m['atlas_sha256'],'hash mismatch');check(len(raw)==4*n*w*h*d,'raw size');check(cols>0 and rows==math.ceil(n/cols) and [cols*w,rows*h]==m['atlas_size'] and max(m['atlas_size'])<=2048,'atlas shape');vol=np.frombuffer(raw,np.uint8).reshape(n,d,h,w,4);img=Image.open(root/'fallback.png').convert('RGBA');check(img.size==(cols*w,rows*h),'atlas mismatch');frames=np.stack([np.asarray(img.crop((i%cols*w,i//cols*h,i%cols*w+w,i//cols*h+h))) for i in range(n)]);
    for a,label in [(vol,'volume'),(frames,'projection')]:
        # Compare alpha and premultiplied colors, not hidden RGB in empty space.
        v=a.astype(np.float32)/255;v[...,:3]*=v[...,3:4];check(np.all(v[...,3].reshape(n,-1).max(1)>.01),label+' empty frame');motion=np.abs(np.diff(v,axis=0)).reshape(n-1,-1).mean(1);med=float(np.median(motion));check(med>.00005 and (motion>.000025).mean()>=.8,label+' static or repeated');check(float(np.abs(v[0]-v[-1]).mean())<=max(.01,4*med),label+' loop seam');
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pack',type=Path);audit(p.parse_args().pack)
