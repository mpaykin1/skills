#!/usr/bin/env python3
"""Bake a CPU surface-normal/roughness atlas for a true 3D RGBA sprite stack.

Input occupancy comes from original posed 3D meshes, never from a 2D billboard.
Atlas RGB is a unit outward surface normal mapped to 0..255; alpha is roughness
for occupied cells. Both maps share the exact source position/scale/pivot.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image


def surface_atlas(volume, spacing, roughness=0.76, blur=0.85):
    if volume.ndim != 4 or volume.shape[-1] != 4:
        raise ValueError('Expected (Z,Y,X,RGBA) stack')
    z,y,x,_ = volume.shape
    if min(z,y,x) < 3 or max(z,y,x)>512:
        raise ValueError('Invalid volume shape')
    if not (0.05 <= float(roughness) <= 1.0):
        raise ValueError('Roughness must be in [0.05, 1.0]')
    if len(spacing)!=3 or not all(math.isfinite(float(s)) and s>0 for s in spacing):
        raise ValueError('Invalid voxel spacing')
    occupied=(volume[...,3] >= 128)
    if not occupied.any():raise ValueError('Empty occupied volume')
    # A Gaussian-smoothed occupancy field supplies meaningful gradients at
    # the boundary without changing the actual occupied geometry.
    field=gaussian_filter(np.pad(occupied.astype(np.float32),2),sigma=blur)[2:-2,2:-2,2:-2]
    gz,gy,gx=np.gradient(field,float(spacing[2]),float(spacing[1]),float(spacing[0]),edge_order=1)
    normal=-np.stack([gx,gy,gz],axis=-1)
    magnitude=np.linalg.norm(normal,axis=-1,keepdims=True)
    normal=np.divide(normal,np.maximum(magnitude,1e-8))
    # Interior normals are unused by first-hit raymarch; store deterministic
    # fallback for flat regions instead of NaNs.
    null=magnitude[...,0]<1e-6
    normal[null]=[0.,0.,1.]
    data=np.zeros(volume.shape,dtype=np.uint8)
    data[...,:3]=np.clip(np.rint((normal*.5+.5)*255.),0,255).astype(np.uint8)
    data[...,3]=np.where(occupied,round(roughness*255.),0).astype(np.uint8)
    cols=math.ceil(math.sqrt(z));rows=math.ceil(z/cols)
    atlas=Image.new('RGBA',(x*cols,y*rows))
    for zi in range(z):
        # Match stack.atlas.png row flip exactly.
        part=Image.fromarray(np.ascontiguousarray(data[zi,::-1]),'RGBA')
        atlas.paste(part,((zi%cols)*x,(zi//cols)*y))
    return atlas
