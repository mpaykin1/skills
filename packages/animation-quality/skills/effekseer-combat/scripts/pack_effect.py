"""Pack an actual Effekseer transparent PNG sequence; do not synthesize missing frames."""
import argparse, hashlib, json, math
from pathlib import Path
from PIL import Image
import numpy as np

def pack(src,dst,fps):
    paths=sorted(src.glob('*.png'))
    if not 2<=len(paths)<=240 or not 1<=fps<=60: raise ValueError('2–240 frames, fps 1–60')
    frames=[Image.open(p).convert('RGBA') for p in paths]; w,h=frames[0].size
    if any(f.size!=(w,h) for f in frames): raise ValueError('unequal dimensions')
    if w*h*len(frames)>16_777_216: raise ValueError('atlas budget exceeded')
    a=[np.asarray(f).copy() for f in frames];
    for f in a: f[f[:,:,3]==0]=0
    hashes=[hashlib.sha256(f.tobytes()).hexdigest() for f in a]
    if len(set(hashes))<max(2,math.ceil(len(a)*.5)): raise ValueError('static or repeated export')
    if not any(np.any(f[:,:,3]) for f in a): raise ValueError('empty effect')
    cols=min(4096//w,math.ceil(math.sqrt(len(a)))); rows=math.ceil(len(a)/cols) if cols else 0
    if not cols or rows*h>4096: raise ValueError('atlas dimension budget exceeded')
    dst.mkdir(parents=True,exist_ok=False); atlas=Image.new('RGBA',(cols*w,rows*h))
    for i,f in enumerate(a): atlas.paste(Image.fromarray(f),(i%cols*w,i//cols*h))
    out=dst/'effect.png';atlas.save(out);meta=dict(schema='effekseer-combat-v1',count=len(a),fps=fps,duration=len(a)/fps,width=w,height=h,columns=cols,rows=rows,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),frameHashes=hashes)
    (dst/'effect.json').write_text(json.dumps(meta,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--fps',type=float,default=30);a=p.parse_args();pack(a.source,a.output,a.fps)
