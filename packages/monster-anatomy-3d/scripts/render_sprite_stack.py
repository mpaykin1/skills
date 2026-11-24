#!/usr/bin/env python3
"""CPU render of real sprite-stacked slices from all azimuths incl. top/bottom.

Uses 3D digital differential analysis (DDA), not flat-picture rotation.
Output is an independent 360 GIF and six transparent key-view PNGs.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image


def load_stack(path):
    path=Path(path).resolve();j=json.loads(path.read_text(encoding='utf8'))
    if j.get('format')!='monster-sprite-stack-v2':raise ValueError('Expected genuine sprite stacking v2 manifest')
    layers=j['layers'];dims=j['dimensions']
    if len(layers)!=dims[2] or len(set(layers))!=len(layers):raise ValueError('Frame/layer mismatch')
    imgs=[np.asarray(Image.open(path.parent/f).convert('RGBA'))[::-1] for f in layers]
    vol=np.stack(imgs)
    if vol.shape!=tuple([dims[2],dims[1],dims[0],4]):raise ValueError('Layer shape mismatch')
    if not (vol[...,3]>0).any():raise ValueError('Empty stack')
    return vol,np.asarray(j['spacing'],float),np.asarray(j['pivot'],float)


def render(vol,step,pivot,yaw,pitch,out_size=128):
    # Camera sees local origin in +Z-up right-handed coordinate system.
    theta,phi=np.deg2rad([yaw,pitch]);eye=np.array([math.cos(phi)*math.sin(theta),-math.cos(phi)*math.cos(theta),math.sin(phi)])
    right=np.array([math.cos(theta),math.sin(theta),0.0])
    up=np.cross(eye,right)
    nx,ny,nz=vol.shape[2],vol.shape[1],vol.shape[0]
    dims=np.array([nx,ny,nz]);box=dims*step;half=box/2
    radius=float(np.linalg.norm(half)*1.5)
    n=out_size;coords=(np.arange(n)+.5-n/2)*2*radius/n
    origins=(pivot+eye*radius+coords[None,:,None]*right-coords[:,None,None]*up).reshape(-1,3)
    direction=-eye
    moving=np.abs(direction)>1e-10
    safe=np.where(moving,direction,1.0)
    t0=(-half+pivot-origins)/safe;t1=(half+pivot-origins)/safe
    near=np.where(moving,np.minimum(t0,t1),-np.inf)
    far=np.where(moving,np.maximum(t0,t1),np.inf)
    begin=np.maximum(np.max(near,axis=1),0.0)
    end=np.min(far,axis=1)
    along=np.all(moving | ((origins>=pivot-half)&(origins<=pivot+half)),axis=1)
    idx=np.flatnonzero(along &(end>begin))
    pixels=np.zeros((n*n,4),np.uint8)
    if len(idx):
        o=origins[idx]
        t=begin[idx]+float(min(step))*1e-7
        vindex=np.clip(np.floor((o+t[:,None]*direction-(pivot-half))/step).astype(int),0,dims-1)
        jump=np.sign(direction).astype(int)
        boundary=(vindex+(jump>0))*step+pivot-half
        tnext=np.where(moving,(boundary-o)/safe,np.inf)
        dt=np.where(moving,step/np.abs(safe),np.inf)
        for _ in range(int(dims.sum())+4):
            if not len(idx):break
            rgba=vol[vindex[:,2],vindex[:,1],vindex[:,0]]
            hit=rgba[:,3]>=128
            pixels[idx[hit]]=rgba[hit]
            remaining=~hit
            idx=idx[remaining];vindex=vindex[remaining];tnext=tnext[remaining]
            if not len(idx):break
            closest=tnext.min(axis=1)
            axes=tnext<=closest[:,None]+1e-11
            vindex+=axes*jump
            tnext=np.where(axes,tnext+dt,tnext)
            keep=(closest<end[idx])&((vindex>=0)&(vindex<dims)).all(axis=1)
            idx=idx[keep];vindex=vindex[keep];tnext=tnext[keep]
    return Image.fromarray(pixels.reshape(n,n,4),'RGBA')


def save_gif(frames,filepath,fps):
    # One global palette, reserved index 255 for full transparency.
    samples=[]
    for f in frames:
        arr=np.asarray(f)
        visible=arr[arr[:,:,3]>=128,:3]
        if len(visible):samples.append(visible[::max(1,len(visible)//800)])
    if not samples:raise ValueError('GIF frames are all empty')
    rgb=np.concatenate(samples).reshape(1,-1,3)
    palette=Image.fromarray(rgb,'RGB').quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    pals=palette.getpalette()[:765]+[0,0,0]
    imgs=[]
    for f in frames:
        pixels=np.asarray(f);palette_im=f.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)
        labels=np.asarray(palette_im).copy()
        labels[pixels[:,:,3]<128]=255
        indexed=Image.fromarray(labels,'P');indexed.putpalette(pals);imgs.append(indexed)
    imgs[0].save(filepath,save_all=True,append_images=imgs[1:],duration=round(1000/fps),loop=0,
                 transparency=255,disposal=2,optimize=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stack');ap.add_argument('output')
    ap.add_argument('--frames',type=int,default=36);ap.add_argument('--size',type=int,default=128)
    ap.add_argument('--fps',type=int,default=20)
    args=ap.parse_args()
    if not 36<=args.frames<=144:ap.error('For full turn, 36..144 frames')
    vol,spacing,pivot=load_stack(args.stack)
    target=Path(args.output).resolve();target.mkdir(parents=True,exist_ok=True)
    poses=[('front',180,0),('back',0,0),('left',270,0),('right',90,0),('top',0,90),('bottom',0,-90)]
    for name,yaw,pitch in poses:render(vol,spacing,pivot,yaw,pitch,args.size).save(target/(name+'.png'))
    save_gif([render(vol,spacing,pivot,360*i/args.frames,18,args.size) for i in range(args.frames)],
             target/'orbit_360.gif',args.fps)
    print('[sprite stacking] orbit:',target/'orbit_360.gif')

if __name__=='__main__':main()
