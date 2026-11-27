# BLOCKWILD Evolution v0.5 — Build-time native-CPU volumetric surface relighting.
# Original implementation; uses BSD-licensed SciPy/Numba, MIT Pillow, BSD NumPy.
# Preserves same occupancy/color volumes; no external models, no GPU requirement.
"""Original 3D source volume -> softly shaded 8-view RGBA projection; CPU JIT, build time only."""
import io, math, base64, json, sys, time
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from scipy.ndimage import gaussian_filter
from numba import njit, prange

@njit(inline='always')
def sample3(g,y,z,x):
    if x<0 or z<0 or y<0 or x>=46.999 or z>=46.999 or y>=62.999:return 0.
    x0=int(x);z0=int(z);y0=int(y);dx=x-x0;dz=z-z0;dy=y-y0
    a=g[y0,z0,x0]*(1-dx)*(1-dz)+g[y0,z0,x0+1]*dx*(1-dz)+g[y0,z0+1,x0]*(1-dx)*dz+g[y0,z0+1,x0+1]*dx*dz
    b=g[y0+1,z0,x0]*(1-dx)*(1-dz)+g[y0+1,z0,x0+1]*dx*(1-dz)+g[y0+1,z0+1,x0]*(1-dx)*dz+g[y0+1,z0+1,x0+1]*dx*dz
    return a*(1-dy)+b*dy

@njit(cache=True,parallel=True)
def cast(occ,r,g,b,scale=1.0):
    W=int(320*scale);H=int(302*scale)
    out=np.zeros((H,W,4),dtype=np.uint8)
    # Same isometric projection as original volume renderer.
    for py in prange(H):
      sy=(py+.5)/scale
      for px in range(W):
        sx=(px+.5)/scale
        delta=(sx-160)/1.92
        # q controls distance along x/z diagonal, rays proceed from front/top.
        for step in range(100):
           q=31-step*.66
           x=24+delta*.5+q;z=24-delta*.5+q
           y=(256+.91+1.82*q-sy)/2.57
           if x<.1 or z<.1 or x>46.9 or z>46.9 or y<.1 or y>62.9:continue
           density=sample3(occ,y,z,x)
           if density>.38:
             nx=sample3(occ,y,z,x-1)-sample3(occ,y,z,x+1)
             nz=sample3(occ,y,z-1,x)-sample3(occ,y,z+1,x)
             ny=sample3(occ,y-1,z,x)-sample3(occ,y+1,z,x)
             nm=math.sqrt(nx*nx+ny*ny+nz*nz)+.00001
             nx/=nm;ny/=nm;nz/=nm
             # Upper-left sun, diffuse key + cool bouncing fill + soft rim.
             dot=max(0.,nx*(-.43)+ny*.76+nz*(-.49))
             rim=max(0.,nx*.66+ny*.38+nz*.68)
             shine=(dot**9)*.065
             shade=min(1.27,.54+dot*.55+rim*.075+shine)
             # Hemisphere lighting, stylized painterly warmth, not unlit voxels.
             cr=sample3(r,y,z,x);cg=sample3(g,y,z,x);cb=sample3(b,y,z,x)
             cr=cr*shade+19*max(0,ny)+8*rim
             cg=cg*(shade*.965)+12*max(0,ny)+5*rim
             cb=cb*(shade*.91)+4*max(0,ny)+7*rim
             out[py,px,0]=min(255,max(0,int(cr)))
             out[py,px,1]=min(255,max(0,int(cg)))
             out[py,px,2]=min(255,max(0,int(cb)))
             out[py,px,3]=255
             break
    return out

def render_smooth(v,palette,scale=1.0):
    mask=(v>0).astype(np.float32)
    occ=gaussian_filter(mask,.96)
    rgb=np.zeros((*v.shape,3),np.float32)
    for k,col in palette.items():rgb[v==k]=col
    denom=gaussian_filter(mask,.7)+1e-4
    color=[np.ascontiguousarray(gaussian_filter(rgb[:,:,:,k],.7)/denom,dtype=np.float32) for k in range(3)]
    raw=cast(np.ascontiguousarray(occ),*color,scale)
    im=Image.fromarray(raw,'RGBA')
    # Subpixel transparency and anti-aliased edge (no posterized squares)
    alpha=im.getchannel('A').filter(ImageFilter.GaussianBlur(.8*scale))
    im.putalpha(alpha)
    bbox=im.getbbox()
    if not bbox:return None
    margin=int(5*scale)
    left=max(0,bbox[0]-margin);top=max(0,bbox[1]-margin);right=min(im.width,bbox[2]+margin);bottom=min(im.height,bbox[3]+margin)
    im=im.crop((left,top,right,bottom))
    if scale>1:
      im=im.resize((max(1,round(im.width/scale)),max(1,round(im.height/scale))),Image.Resampling.LANCZOS)
      left=round(left/scale);top=round(top/scale)
    buf=io.BytesIO();im.save(buf,format='PNG',optimize=True,compress_level=7)
    return {'uri':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(), 'base':[160-left,256-top], 'size':list(im.size), 'layers':int(np.count_nonzero(np.any(v!=0,axis=(1,2))))}

