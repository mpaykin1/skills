#!/usr/bin/env python3
"""Opt-in OpenImageIO CPU image metadata inspection / explicit EXR lightmap conversion.

Never mutates a source file or any original game texture. Supports color-managed
HDR EXR/HDR/TIFF -> 16-bit PNG as a derivative *only* when the caller declares
source color space. AO is non-color data and must NOT be gamma converted.
Uses the real oiiotool executable; no download, dummy image, or renderer fallback.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ACCEPTED = {'.png', '.exr', '.hdr', '.tif', '.tiff'}
HDR = {'.exr', '.hdr', '.tif', '.tiff'}


def find_tool(arg: str | None) -> str:
    exe = arg or shutil.which('oiiotool')
    if exe is None:
        raise RuntimeError('OpenImageIO oiiotool executable is missing; install official OpenImageIO')
    if arg:
        candidate = Path(arg).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(arg)
        if found:
            return found
        raise RuntimeError('oiiotool not found: '+arg)
    return exe


def call(cmd: list[str], timeout=120) -> str:
    r=subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode:
        raise RuntimeError('OpenImageIO failed: '+(r.stderr or r.stdout)[-1500:])
    return r.stdout


def inspect(path: Path, exe: str) -> dict:
    path=path.resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in ACCEPTED:
        raise ValueError('Expected existing PNG/EXR/HDR/TIFF lightmap')
    info=call([exe,'--info','-v',str(path)])
    if not info.strip():
        raise RuntimeError('OpenImageIO returned empty image information')
    # OIIO input info includes size/depth and metadata, but their human-readable
    # spelling varies by version. Keep raw info instead of inventing color tags.
    colors=[s.strip() for s in info.splitlines() if 'colorspace' in s.lower()]
    dims=re.search(r'(?<!\d)(\d{1,6})\s*x\s*(\d{1,6})(?:\s*x\s*(\d+))?',info)
    return {'name':path.name,'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'dimensions':list(map(int,dims.groups()[:2])) if dims else None,
            'colorspace_metadata':colors[:6], 'oiio_info':info[:2000]}


def convert(src: Path, dst: Path, exe: str, kind: str, from_space: str | None,
            to_space: str, depth: int) -> dict:
    src=src.resolve(strict=True)
    dst=dst.expanduser().resolve()
    if src.suffix.lower() not in HDR or dst.suffix.lower()!='.png':
        raise ValueError('Input must be EXR/HDR/TIFF and output must be PNG')
    if src==dst or dst.exists():
        raise ValueError('Output must be a new file; originals and existing assets cannot be overwritten')
    if kind=='color' and not from_space:
        raise ValueError('Color lightmap conversion requires explicit --from-space (e.g. lin_rec709_scene)')
    if kind=='data' and from_space:
        raise ValueError('Non-color AO/data maps cannot use --from-space; no gamma/color conversion is performed')
    if depth!=16:
        raise ValueError('Only 16-bit PNG derivatives are supported')
    info_before=inspect(src,exe)
    dst.parent.mkdir(parents=True,exist_ok=True)
    temporary=dst.with_name(dst.name+'.partial.png')
    if temporary.exists():
        raise ValueError('Temporary output already exists; refusing to overwrite')
    command=[exe,str(src)]
    if kind=='color':
        command+=['--colorconvert',from_space,to_space]
    command+=['-d','uint16','-o',str(temporary)]
    try:
        call(command, timeout=300)
        if not temporary.is_file() or temporary.stat().st_size<24:
            raise RuntimeError('OpenImageIO produced no usable PNG')
        # Check the output is readable by the actual OIIO decoder and sizes agree.
        after=inspect(temporary,exe)
        if info_before['dimensions'] and after['dimensions'] and info_before['dimensions']!=after['dimensions']:
            raise RuntimeError('OpenImageIO unexpectedly changed lightmap dimensions')
        temporary.rename(dst)
    finally:
        temporary.unlink(missing_ok=True)
    return {'source':str(src),'output':str(dst),'kind':kind,
            'input_colorspace':from_space if kind=='color' else 'data/untransformed',
            'output_colorspace':to_space if kind=='color' else 'data/untransformed',
            'out_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
            'original_untouched':True,
            'note':'Import AO as linear/non-color data; review color lightmaps in the target renderer.'}


def main():
    p=argparse.ArgumentParser(description='OpenImageIO non-destructive baked-lightmap image utility')
    sub=p.add_subparsers(dest='action',required=True)
    inf=sub.add_parser('inspect',help='Verify baked PNG/EXR/HDR/TIFF in OpenImageIO and show metadata')
    inf.add_argument('--input',type=Path,required=True)
    inf.add_argument('--oiiotool',help='Path to installed OpenImageIO oiiotool')
    conv=sub.add_parser('convert',help='Create a 16-bit PNG derivative from HDR lightmap')
    conv.add_argument('--input',type=Path,required=True)
    conv.add_argument('--out',type=Path,required=True)
    conv.add_argument('--kind',choices=['color','data'],required=True,
                      help='color uses explicit colorspace conversion; data/AO never gamma converts')
    conv.add_argument('--from-space',help='Required for --kind color: source space, e.g. lin_rec709_scene')
    conv.add_argument('--to-space',default='srgb_rec709_scene',help='Destination for color lightmaps (default sRGB)')
    conv.add_argument('--depth',type=int,default=16)
    conv.add_argument('--oiiotool',help='Path to installed OpenImageIO oiiotool')
    a=p.parse_args()
    tool=find_tool(a.oiiotool)
    if a.action=='inspect':result=inspect(a.input,tool)
    else:result=convert(a.input,a.out,tool,a.kind,a.from_space,a.to_space,a.depth)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        sys.exit('ERROR: '+str(error))
