"""Bakes a rights-approved user reference into an authored stone-only material.
The reference stays on the owner's machine. No downloaded model or texture.
Requires Pillow and NumPy; no GPU or internet. Output is regular PNG.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
P=argparse.ArgumentParser()
P.add_argument('--reference-image',type=Path,required=True,help='Owner-approved image to sample stone texture from')
P.add_argument('--out',type=Path,required=True)
a=P.parse_args()
ref=np.asarray(Image.open(a.reference_image).convert('RGB'))
rng=np.random.default_rng(16027)
h,w=ref.shape[:2]
if min(h,w)<150:raise ValueError('Reference too small for stone material')
samples=[]
for i in range(4000):
 x=int(rng.integers(max(0,round(165*w/864)),max(16,round(790*w/864))))
 y=int(rng.integers(max(0,round(410*h/1536)),max(16,round(1150*h/1536))))
 roi=ref[y:y+15,x:x+15]
 if roi.shape!=(15,15,3):continue
 r,g,b=[roi[:,:,i].astype(int) for i in range(3)]
 good=((r>88)&(r<235)&(g>77)&(g<226)&(b>70)&(b<225)&((r-g)>2)&((r-b)>10)&((r-b)<65))
 if good.mean()<.92:continue
 st=roi.astype(np.float32).std(axis=(0,1)).mean()
 if 4<=st<=24:samples.append(roi)
if len(samples)<25:raise ValueError('Insufficient matching stone-only pixels; use a clearer reference')
T=13;extent=124;canvas=np.empty((extent*T,extent*T,3),np.uint8)
cols=np.array([[199,179,158],[215,195,177],[192,181,171],[208,186,172],
[196,173,158],[215,200,183],[188,177,168],[217,187,165],[205,190,182],[197,184,174]],np.float32)
for iz in range(extent):
 for ix in range(extent):
  src=samples[(ix*131+iz*491)%len(samples)][1:14,1:14].astype(np.float32)
  rough=(src-src.mean(axis=(0,1),keepdims=True))*.45
  sel=cols[int(rng.integers(len(cols)))].copy()
  sel+=rng.normal(0,3.5,3)
  patch=np.clip(sel[None,None,:]+rough,0,255)
  patch[0]=np.clip(patch[0]*.85-1,0,255);patch[:,0]=np.clip(patch[:,0]*.90-2,0,255)
  patch[-1]=np.clip(patch[-1]*1.045+2,0,255);patch[:,-1]=np.clip(patch[:,-1]*1.04+1,0,255)
  if rng.random()<.24:
   yy=int(rng.integers(3,T-3));xx=int(rng.integers(2,T-4))
   patch[yy,xx:xx+int(rng.integers(2,5))]-=rng.uniform(8,20)
  if rng.random()<.16:
   xx=int(rng.integers(2,T-2));yy=int(rng.integers(2,T-2));patch[yy,xx]+=np.array([8,8,8])
  canvas[iz*T:(iz+1)*T,ix*T:(ix+1)*T]=np.clip(patch,0,255).astype(np.uint8)
a.out.parent.mkdir(parents=True,exist_ok=True)
Image.fromarray(canvas,'RGB').save(a.out,optimize=True)
print('Stone texture',a.out,a.out.stat().st_size,'samples',len(samples))
