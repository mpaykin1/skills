#!/usr/bin/env python3
"""Render an RGBA slice volume from any orthographic angle. Requires numpy and Pillow.
Usage: python render_stack.py stack.json output_dir --mode all
Alpha is an occupancy mask (>=128); not a translucent-volume integrator.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from PIL import Image


def load(path):
    p=Path(path); m=json.loads(p.read_text()); files=m['layers']
    if not files or len(set(files))!=len(files): raise ValueError('Need distinct ordered layer paths')
    v=np.stack([np.asarray(Image.open(p.parent/f).convert('RGBA')) for f in files])
    spacing=np.array(m['spacing'],float); pivot=np.array(m.get('pivot',[0,0,0]),float)
    if spacing.shape!=(3,) or pivot.shape!=(3,) or not np.isfinite(spacing).all() or not np.isfinite(pivot).all() or (spacing<=0).any(): raise ValueError('Invalid spacing or pivot')
    if not (v[...,3]>=128).any(): raise ValueError('Empty stack')
    return v,spacing,pivot,int(m.get('size',384))


def render(v,s,pivot,size,yaw,pitch,aa=1):
    a,b=np.radians([yaw,pitch]); right=np.array([np.cos(a),np.sin(a),0.]); eye=np.array([np.sin(a)*np.cos(b),-np.cos(a)*np.cos(b),np.sin(b)]); up=np.cross(eye,right)
    nz,ny,nx=v.shape[:3]; dims=np.array([nx,ny,nz]); half=dims*s/2
    radius=np.linalg.norm(half+np.abs(pivot))*1.05
    n=size*aa; coord=(np.arange(n)+.5-n/2)*2*radius/n
    origins=(pivot+coord[None,:,None]*right-coord[:,None,None]*up+eye*radius).reshape(-1,3)
    # Exact grid DDA, first occupied cell wins. Handles edge-on and pole views.
    direction=-eye; direction[np.abs(direction)<1e-12]=0
    moving=direction!=0
    safe=np.where(moving,direction,1.)
    ta=(-half-origins)/safe; tb=(half-origins)/safe
    near=np.where(moving,np.minimum(ta,tb),-np.inf); far=np.where(moving,np.maximum(ta,tb),np.inf)
    start=np.maximum(near.max(axis=1),0); end=far.min(axis=1)
    parallel_ok=np.all(moving | ((origins>=-half)&(origins<=half)),axis=1)
    active=np.flatnonzero(parallel_ok & (end>start))
    out=np.zeros((n*n,4),np.uint8)
    if active.size:
        o=origins[active]; t=start[active]+min(s)*1e-8
        pos=o+t[:,None]*direction
        cell=np.clip(np.floor((pos+half)/s).astype(int),0,dims-1)
        step=np.sign(direction).astype(int)
        boundary=(cell+(step>0))*s-half
        tmax=np.where(moving,(boundary-o)/safe,np.inf)
        tdelta=np.where(moving,s/np.abs(safe),np.inf)
        for _ in range(int(dims.sum())+3):
            if not active.size: break
            color=v[cell[:,2],ny-1-cell[:,1],cell[:,0]]; hit=color[:,3]>=128
            out[active[hit]]=color[hit]; out[active[hit],3]=255
            keep=~hit; active=active[keep]; cell=cell[keep]; tmax=tmax[keep]
            if not active.size: break
            tnext=tmax.min(axis=1); axes=tmax<=tnext[:,None]+1e-10
            cell+=axes*step; tmax=np.where(axes,tmax+tdelta,tmax)
            keep=(tnext<end[active]) & ((cell>=0)&(cell<dims)).all(axis=1)
            active=active[keep]; cell=cell[keep]; tmax=tmax[keep]
    image=Image.fromarray(out.reshape(n,n,4),'RGBA')
    return image.resize((size,size),Image.Resampling.LANCZOS) if aa>1 else image


def gif(frames,path,duration):
    # Shared 255-color palette, index 255 reserved for transparency.
    samples=[]
    for im in frames:
        a=np.asarray(im); rgb=a[a[...,3]>=128,:3]
        if len(rgb): samples.append(rgb[::max(1,len(rgb)//3500)])
    if not samples: raise ValueError('All frames empty')
    sample=np.concatenate(samples); palette=Image.fromarray(sample.reshape(1,-1,3),'RGB').quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    pal=(palette.getpalette()[:765]+[0,0,0]); palette.putpalette(pal)
    indexed=[]
    for im in frames:
        p=im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)
        idx=np.array(p); opaque=np.asarray(im)[...,3]>=128
        if ((idx==255)&opaque).any():
            # Reserved index must never be used by visible pixels.
            idx[(idx==255)&opaque]=int(np.argmin(np.sum(np.array(pal[:765]).reshape(255,3).astype(float)**2,axis=1)))
        idx[~opaque]=255; f=Image.fromarray(idx,'P'); f.putpalette(pal); indexed.append(f)
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=duration,loop=0,disposal=2,transparency=255,optimize=False)


def aim():
    # Camera-relative orbit simulates rigid object aiming. Separate full profiles.
    poses=[]
    for yaw,pitch in [(90,0),(-90,0),(0,-90),(0,90)]:
        for k in range(24):
            u=(1-math.cos(2*math.pi*k/24))/2; poses.append((yaw*u,pitch*u))
    return poses


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('stack'); p.add_argument('output'); p.add_argument('--mode',choices=['all','orbit','sphere','aim','views'],default='all');p.add_argument('--frames',type=int,default=36);p.add_argument('--size',type=int);p.add_argument('--aa',type=int,choices=[1,2,3],default=1);p.add_argument('--duration',type=int,default=50); a=p.parse_args()
    if a.frames<36 or a.duration<10: p.error('minimum 36 orbit frames, duration >=10ms')
    v,s,pivot,size=load(a.stack);size=a.size or size
    if size<16: p.error('size >=16')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    def r(y,b):return render(v,s,pivot,size,y,b,a.aa)
    if a.mode in ['all','views']:
        for name,y,b in [('rear',0,0),('right',90,0),('front',180,0),('left',270,0),('top',0,90),('bottom',0,-90),('rear_right',45,25),('front_right',135,25),('front_left',225,25),('rear_left',315,25)]: r(y,b).save(out/(name+'.png'))
    if a.mode in ['all','orbit']:gif([r(i*360/a.frames,20) for i in range(a.frames)],out/'orbit_360.gif',a.duration)
    if a.mode in ['all','sphere']:
        n=max(72,a.frames*2);gif([r(360*i/n,90*math.sin(2*math.pi*i/n)) for i in range(n)],out/'sphere.gif',a.duration)
    if a.mode in ['all','aim']:gif([r(y,b) for y,b in aim()],out/'aim.gif',a.duration)

if __name__=='__main__':main()
