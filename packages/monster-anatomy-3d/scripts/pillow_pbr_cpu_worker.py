#!/usr/bin/env python3
"""Real Pillow 12.3.0 CPU rasterizer for UV-resolved surface curvature PBR.

Input: immutable Blender-exported UV triangle data. Output: embedded-ready
albedo and linear roughness PNG images. No GPU, procedural noise patterns,
texture downloads, imported hero replacement or geometry mutation.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sys


def clamp(value, lo, hi):
    return min(hi, max(lo, value))


def render(data, color_path: Path, roughness_path: Path):
    from PIL import Image, __version__ as pillow_version
    if pillow_version != '12.3.0':
        raise RuntimeError('Expected real Pillow==12.3.0, installed: '+pillow_version)
    if data.get('format')!='monster-pillow-pbr-v1':
        raise ValueError('Wrong input format')
    size=data.get('size',512)
    if type(size)!=int or size<128 or size>2048 or size & (size-1):
        raise ValueError('Texture size must be a power of two: 128..2048')
    triangles=data.get('triangles')
    if not isinstance(triangles,list) or not 1<=len(triangles)<=200000:
        raise ValueError('Invalid triangle count')
    color=data.get('base_color')
    if not isinstance(color,list) or len(color)!=3 or not all(isinstance(x,(float,int)) and math.isfinite(x) and 0<=x<=1 for x in color):
        raise ValueError('Base color must be three finite linear 0..1 components')
    rough=float(data.get('roughness',0.5));wetness=float(data.get('wetness',0.35))
    if not all(math.isfinite(v) for v in (rough,wetness)) or not 0<=rough<=1 or not 0<=wetness<=1:
        raise ValueError('Invalid roughness / wetness')
    # Blender's Principled base-color default is linear; PNG sRGB encoding
    # must be applied once, to avoid darkening the artist's approved colors.
    def linear_to_srgb(x):
        return 12.92*x if x<=0.0031308 else 1.055*(x**(1/2.4))-0.055
    srgb=[clamp(linear_to_srgb(c),0,1) for c in color]
    default_color=tuple(round(255*c) for c in srgb)
    rough_dry=clamp(rough*(1-0.52*wetness),0.06,1.0)
    rgba=bytearray(bytes((*default_color,255))* (size*size))
    rvalues=bytearray(bytes((round(255*rough_dry),))*size*size)
    painted=0
    for tri in triangles:
        uv=tri.get('uv');curvature=tri.get('curvature')
        if not isinstance(uv,list) or len(uv)!=3 or not isinstance(curvature,list) or len(curvature)!=3:
            raise ValueError('Each triangle needs 3 UV pairs and 3 curvature values')
        if any(not isinstance(p,list) or len(p)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) and -1e-4<=v<=1.0001 for v in p) for p in uv):
            raise ValueError('UV outside atlas / nonfinite')
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in curvature):
            raise ValueError('Nonfinite / invalid curvature')
        pts=[(clamp(float(u),0,1)*(size-1),(1-clamp(float(v),0,1))*(size-1)) for u,v in uv]
        (ax,ay),(bx,by),(cx,cy)=pts
        denom=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(denom)<1e-9:continue
        minx=max(0,int(math.floor(min(ax,bx,cx))));maxx=min(size-1,int(math.ceil(max(ax,bx,cx))))
        miny=max(0,int(math.floor(min(ay,by,cy))));maxy=min(size-1,int(math.ceil(max(ay,by,cy))))
        c1,c2,c3=map(float,curvature)
        for py in range(miny,maxy+1):
            for px in range(minx,maxx+1):
                x=px+.5;y=py+.5
                wa=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/denom
                wb=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/denom
                wc=1-wa-wb
                if min(wa,wb,wc)<-1e-5:continue
                intensity=clamp(wa*c1+wb*c2+wc*c3,0,1)
                # Creases are sculpt-derived, not randomly patterned. Subtle
                # tonal variation respects original material hues.
                shade=1-0.22*intensity
                index=(py*size+px)
                off=4*index
                rgba[off:off+3]=bytes(round(clamp(c*shade,0,1)*255) for c in srgb)
                rvalues[index]=round(255*clamp(rough_dry+(0.20*intensity)*(1-0.5*wetness),0.05,1))
                painted+=1
    if painted<16:
        raise RuntimeError('UV triangles covered too few pixels; no texture created')
    color_path.parent.mkdir(parents=True,exist_ok=True)
    roughness_path.parent.mkdir(parents=True,exist_ok=True)
    if color_path.resolve()==roughness_path.resolve():raise ValueError('Distinct output paths required')
    Image.frombytes('RGBA',(size,size),bytes(rgba)).save(color_path,format='PNG',optimize=True)
    Image.frombytes('L',(size,size),bytes(rvalues)).save(roughness_path,format='PNG',optimize=True)
    if min(color_path.stat().st_size,roughness_path.stat().st_size)<75:
        raise RuntimeError('Unexpectedly tiny texture file')
    print('[Pillow] CPU surface-aware PBR textures:',size,'px',len(triangles),'faces')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--albedo',required=True,type=Path)
    p.add_argument('--roughness',required=True,type=Path)
    a=p.parse_args()
    if not a.input.is_file():p.error('Input JSON missing')
    if a.input.resolve() in (a.albedo.resolve(),a.roughness.resolve()):p.error('Input cannot be an output')
    data=json.loads(a.input.read_text(encoding='utf-8'))
    render(data,a.albedo,a.roughness)

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,ImportError,RuntimeError) as exc:
        print('[Pillow] ERROR:',exc,file=sys.stderr)
        raise SystemExit(2)
