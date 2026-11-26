#!/usr/bin/env python3
"""Official sprite-in-the-round voxlib: 2–5 authored orthographic views to an actual RGBA slice strip.

Do not generate missing sides with arbitrary symmetry; original art is preserved where possible.
Output is an estimated visual hull, not recovered original 3D or gameplay.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from install_upstream import resolve

def run(folder:Path,output:Path,upstream:Path,rounded:bool=False):
    names=('top','side','front','back','side2')
    if not (folder/'top.png').is_file() or not (folder/'side.png').is_file():
        raise ValueError('2-view minimum: top.png and side.png in input directory')
    sys.path.insert(0,str(upstream/'scripts'))
    from voxlib import load,stack_views,save_sheet
    views={}
    for name in names:
        src=folder/(name+'.png')
        if src.exists():
            if src.is_symlink():raise ValueError('View source symlink forbidden')
            with Image.open(src) as im:
                if im.format!='PNG' or max(im.size)>512 or im.size[0]*im.size[1]>262144:
                    raise ValueError('Orthographic view has excessive size')
            views[name]=load(src)
    vol,_=stack_views(**views,strip=False,colors=0,shade_amount=0,rounded=rounded)
    if not isinstance(vol,np.ndarray) or vol.ndim!=4 or vol.shape[3]!=4:
        raise RuntimeError('Official voxlib produced invalid volume shape')
    if vol.shape[0]>192 or max(vol.shape[1:3])>512 or vol.size>128*1024*1024:
        raise ValueError('Official volume exceeds mobile/WebGL2 budget')
    if not np.any(vol[...,3]>=128):raise ValueError('Views produced an empty volume')
    output.parent.mkdir(parents=True,exist_ok=True)
    save_sheet(vol,output)
    print('AUTHORED_VIEWS_TO_STACK:',len(views),'volume:',tuple(vol.shape),'strip:',output)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--upstream-root')
    p.add_argument('--rounded',action='store_true')
    p.add_argument('--no-install-upstream',action='store_true')
    a=p.parse_args()
    src=a.source.expanduser().resolve(strict=True)
    if not src.is_dir():raise ValueError('Source must be a folder with top.png and side.png')
    out=a.out.expanduser().resolve()
    if out==src or src in out.parents or out in src.parents:raise ValueError('Output must be disjoint from source views')
    run(src,out,resolve(a.upstream_root,no_install=a.no_install_upstream),a.rounded)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,ImportError) as exc:sys.exit('ERROR: '+str(exc))
