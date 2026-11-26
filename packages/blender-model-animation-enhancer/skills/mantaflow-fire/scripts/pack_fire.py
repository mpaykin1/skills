"""Pack actual rendered RGBA frames; never synthesize a missing bake."""
import argparse, hashlib, json, math
from pathlib import Path
from PIL import Image
import numpy as np

def pack(root,out):
    meta=json.loads((root/'bake.json').read_text()); assert meta['source']=='blender-mantaflow'
    paths=sorted((root/'frames').glob('*.png')); n=meta['frames']; assert len(paths)==n and 16<=n<=64 and meta['fps']==24
    frames=[Image.open(p).convert('RGBA') for p in paths]; w,h=frames[0].size; assert all(f.size==(w,h) for f in frames); assert (w,h)==(192,256)
    raw=np.stack([np.asarray(f,dtype=np.float32)/255 for f in frames]); alpha=raw[...,3:]; rgb=raw[...,:3]*alpha; data=np.concatenate([rgb,alpha],axis=-1)
    if float(alpha.max())<.1 or np.any(alpha.mean(axis=(1,2,3))<.001): raise ValueError('empty fire frames')
    changes=np.abs(np.diff(data,axis=0)).mean(axis=(1,2,3)); seam=float(np.abs(data[0]-data[-1]).mean()); median=float(np.median(changes));
    if median<.0005 or np.count_nonzero(changes>.00025)<.8*len(changes): raise ValueError('static or repeated effect')
    if seam>max(.025,4*median): raise ValueError('visible loop seam: bake longer/select better segment')
    # Gutters prevent atlas interpolation bleeding; no mipmaps in runtime.
    stride_x=w+2; stride_y=h+2; cols=min(2048//stride_x,n); rows=math.ceil(n/cols); assert rows*stride_y<=2048
    atlas=Image.new('RGBA',(cols*stride_x,rows*stride_y));
    for i,f in enumerate(frames):
        x=(i%cols)*stride_x+1;y=(i//cols)*stride_y+1;atlas.paste(f,(x,y))
        atlas.paste(f.crop((0,0,1,h)),(x-1,y));atlas.paste(f.crop((w-1,0,w,h)),(x+w,y));atlas.paste(f.crop((0,0,w,1)),(x,y-1));atlas.paste(f.crop((0,h-1,w,h)),(x,y+h))
    out.mkdir(parents=True,exist_ok=False); p=out/'fire.png'; atlas.save(p); meta.update({'schema':'mantaflow-flipbook-v1','atlas':'fire.png','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'tile':[w,h],'stride':[stride_x,stride_y],'size':list(atlas.size),'cols':cols,'rows':rows,'light':[round(float(np.mean(np.maximum(rgb[i,...,0]-rgb[i,...,2],0)))*15,4) for i in range(n)],'median_motion':median,'seam':seam,'source_frame_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]}); (out/'fire.json').write_text(json.dumps(meta,indent=2)); return meta
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bake',type=Path);p.add_argument('out',type=Path);a=p.parse_args();pack(a.bake,a.out)
