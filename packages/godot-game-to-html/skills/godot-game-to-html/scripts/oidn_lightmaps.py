#!/usr/bin/env python3
"""Opt-in Intel Open Image Denoise 2 CPU adapter for *baked* AO PNGs.

Calls the upstream OIDN C99 API through ctypes. No OIDN binaries or image
assets are bundled. This is NOT an image super-resolution or color-restorer;
never denoise original hand-authored textures, normal maps, or animated sprites.

CPU OIDN RT filter is used for LDR PNG. RTLightmap (a different OIDN filter)
requires HDR lightmap data and is deliberately not applied to PNG/AO.
"""
from __future__ import annotations
import argparse
import ctypes as C
from ctypes.util import find_library
from pathlib import Path
import os
import sys


def library_path(explicit: str | None = None) -> str:
    # Discover installed official runtime, NEVER fetch or run remote binaries.
    candidates = [explicit, os.environ.get('OIDN_LIBRARY'),
                  find_library('OpenImageDenoise'),
                  'OpenImageDenoise.dll', 'libOpenImageDenoise.so.2',
                  'libOpenImageDenoise.2.dylib']
    last = None
    for candidate in filter(None, candidates):
        try:
            C.CDLL(str(candidate))
            return str(candidate)
        except OSError as err:
            last = err
    raise RuntimeError('Intel OIDN 2 native library not installed or loadable; '
                       'install the official CPU runtime and pass --oidn-lib '
                       '/path/to/libOpenImageDenoise.so.2. ' + str(last))


def open_oidn(lib_path: str):
    dll = C.CDLL(lib_path)
    handle = C.c_void_p
    # OIDNDeviceType CPU=1; OIDNFormat float3=3; OIDNQuality HIGH=6.
    dll.oidnIsCPUDeviceSupported.argtypes = []
    dll.oidnIsCPUDeviceSupported.restype = C.c_bool
    if not dll.oidnIsCPUDeviceSupported():
        raise RuntimeError('OIDN CPU backend unsupported on this machine')
    dll.oidnNewDevice.argtypes = [C.c_int]
    dll.oidnNewDevice.restype = handle
    dll.oidnCommitDevice.argtypes = [handle]
    dll.oidnCommitDevice.restype = None
    dll.oidnNewFilter.argtypes = [handle, C.c_char_p]
    dll.oidnNewFilter.restype = handle
    dll.oidnSetSharedFilterImage.argtypes = [handle,C.c_char_p,handle,C.c_int,
                                               C.c_size_t,C.c_size_t,C.c_size_t,
                                               C.c_size_t,C.c_size_t]
    dll.oidnSetSharedFilterImage.restype = None
    dll.oidnSetFilterBool.argtypes = [handle,C.c_char_p,C.c_bool]
    dll.oidnSetFilterBool.restype = None
    dll.oidnSetFilterInt.argtypes = [handle,C.c_char_p,C.c_int]
    dll.oidnSetFilterInt.restype = None
    dll.oidnCommitFilter.argtypes = [handle]
    dll.oidnCommitFilter.restype = None
    dll.oidnExecuteFilter.argtypes = [handle]
    dll.oidnExecuteFilter.restype = None
    dll.oidnGetDeviceError.argtypes = [handle,C.POINTER(C.c_char_p)]
    dll.oidnGetDeviceError.restype = C.c_int
    dll.oidnReleaseFilter.argtypes = [handle]
    dll.oidnReleaseFilter.restype = None
    dll.oidnReleaseDevice.argtypes = [handle]
    dll.oidnReleaseDevice.restype = None
    return dll


def check_oidn(dll, dev, where: str) -> None:
    msg = C.c_char_p()
    code = dll.oidnGetDeviceError(dev,C.byref(msg))
    if code:
        detail = (msg.value or b'unknown').decode('utf-8','replace')
        raise RuntimeError(f'OIDN {where}: {detail} (code {code})')


def denoise_array(image, dll, strength: float, srgb: bool):
    import numpy as np
    if image.dtype != np.float32 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('Expected H x W x 3 float32 image')
    if not np.isfinite(image).all():
        raise ValueError('Nonfinite input pixels')
    h,w,_ = image.shape
    if w < 16 or h < 16:
        raise ValueError('Denoiser requires a lightmap >=16x16')
    src = np.ascontiguousarray(image, dtype=np.float32)
    dst = np.empty_like(src)
    dev = dll.oidnNewDevice(1)
    if not dev:
        check_oidn(dll,None,'device creation')
        raise RuntimeError('Cannot create OIDN CPU device')
    filt = None
    try:
        dll.oidnCommitDevice(dev)
        check_oidn(dll,dev,'commit device')
        filt = dll.oidnNewFilter(dev,b'RT')
        if not filt:
            check_oidn(dll,dev,'filter creation')
            raise RuntimeError('Cannot create OIDN RT filter')
        # CPU permits caller-owned contiguous memory; no GPU buffers needed.
        dll.oidnSetSharedFilterImage(filt,b'color',C.c_void_p(src.ctypes.data),3,w,h,0,0,0)
        dll.oidnSetSharedFilterImage(filt,b'output',C.c_void_p(dst.ctypes.data),3,w,h,0,0,0)
        dll.oidnSetFilterBool(filt,b'hdr',False)
        dll.oidnSetFilterBool(filt,b'srgb',bool(srgb))
        dll.oidnSetFilterInt(filt,b'quality',6)
        dll.oidnCommitFilter(filt)
        check_oidn(dll,dev,'commit filter')
        dll.oidnExecuteFilter(filt)
        check_oidn(dll,dev,'execute filter')
    finally:
        if filt:
            dll.oidnReleaseFilter(filt)
        dll.oidnReleaseDevice(dev)
    if not np.isfinite(dst).all():
        raise RuntimeError('OIDN returned NaN/Inf; input image untouched')
    return np.clip((1.-strength)*src + strength*dst,0.,1.)


def process_png(source: Path, target: Path, dll, strength:float, srgb:bool):
    import numpy as np
    from PIL import Image
    if source.resolve() == target.resolve():
        raise ValueError('Output must not overwrite source')
    with Image.open(source) as im:
        im.load()
        if im.mode not in ('L','RGB','RGBA','LA'):
            raise ValueError(f'Unsupported PNG mode {im.mode!r}; only 8-bit AO grayscale/RGB')
        mode=im.mode
        alpha = np.asarray(im.getchannel('A')).copy() if 'A' in mode else None
        rgb = np.asarray(im.convert('RGB'),dtype=np.float32) / 255.
    den = denoise_array(rgb,dll,strength,srgb)
    array = np.clip(np.rint(den*255.),0,255).astype(np.uint8)
    if mode in ('L','LA'):
        result=Image.fromarray(array[:,:,0],mode='L')
        if alpha is not None:
            result.putalpha(Image.fromarray(alpha,mode='L'))
    else:
        result=Image.fromarray(array,mode='RGB')
        if alpha is not None:
            result.putalpha(Image.fromarray(alpha,mode='L'))
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.stem+'.partial.png')
    try:
        result.save(temp,optimize=True)
        with Image.open(temp) as check:
            check.load()
            if check.size != (rgb.shape[1],rgb.shape[0]):
                raise RuntimeError('OIDN image dimensions mismatch')
        os.replace(temp,target)
    finally:
        temp.unlink(missing_ok=True)
    return target


def main():
    ap=argparse.ArgumentParser(description='Intel OIDN CPU denoise of baked AO PNG sidecars; originals unchanged')
    source=ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--input',type=Path)
    source.add_argument('--input-dir',type=Path)
    ap.add_argument('--out',type=Path,help='Output PNG for --input')
    ap.add_argument('--out-dir',type=Path,help='Output directory for --input-dir')
    ap.add_argument('--oidn-lib',help='Installed official OIDN 2 shared library')
    ap.add_argument('--strength',type=float,default=0.7,help='Original/detail retention; 0..1, default 0.7')
    ap.add_argument('--linear',action='store_true',help='Input PNG is linear, not sRGB gamma-encoded')
    args=ap.parse_args()
    if not 0.0 <= args.strength <= 1.0:ap.error('--strength must be in [0,1]')
    if args.input and not args.out:ap.error('--out required with --input')
    if args.input_dir and not args.out_dir:ap.error('--out-dir required with --input-dir')
    files=[args.input] if args.input else sorted(args.input_dir.glob('*_AO.png'))
    if not files:raise RuntimeError('No baked *_AO.png lightmaps found; no outputs written')
    dest_dir = args.out_dir.resolve() if args.out_dir else None
    if args.input_dir and (dest_dir == args.input_dir.resolve() or args.input_dir.resolve() in dest_dir.parents):
        raise ValueError('Output directory must be independent from source directory')
    if args.input_dir and dest_dir in args.input_dir.resolve().parents:
        raise ValueError('Output may not overlap source directory')
    dll=open_oidn(library_path(args.oidn_lib))
    output=[]
    for f in files:
        f=f.resolve(strict=True)
        if f.suffix.lower()!='.png':raise ValueError('Only baked PNG lightmaps supported')
        dst=(dest_dir/(f.stem+'_oidn.png')) if dest_dir else args.out.resolve()
        process_png(f,dst,dll,args.strength,not args.linear)
        output.append({'source':str(f),'denoised':str(dst)})
    for entry in output:print('OIDN CPU AO:',entry['denoised'])
    print(f'OIDN RT LDR: {len(output)} maps; strength={args.strength}; original inputs unchanged')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,ImportError) as err:
        sys.exit('ERROR: '+str(err))
