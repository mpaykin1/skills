#!/usr/bin/env python3
"""Validate actual GIF containers and package them. Pillow required."""
import argparse, hashlib, zipfile
from pathlib import Path
from PIL import Image

def inspect(path, opaque=False, wide=False):
    with Image.open(path) as im:
        if im.format != 'GIF': raise ValueError(f'{path}: not GIF')
        n, size = im.n_frames, im.size
        if not 8 <= n <= 12: raise ValueError(f'{path}: {n} frames')
        if im.info.get('loop') != 0: raise ValueError(f'{path}: not infinite loop')
        if wide and (size[0] < 1280 or size[1] < 720): raise ValueError(f'{path}: too small')
        hashes = set()
        for i in range(n):
            im.seek(i)
            rgba = im.convert('RGBA')
            if rgba.size != size or im.info.get('duration', 0) <= 0: raise ValueError(f'{path}: invalid frame {i}')
            lo, hi = rgba.getchannel('A').getextrema()
            if not opaque and (lo != 0 or hi != 255): raise ValueError(f'{path}: missing transparency or visible content at {i}')
            hashes.add(hashlib.sha256(rgba.tobytes()).digest())
        if len(hashes) < 2: raise ValueError(f'{path}: no motion')
        return size, n

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--opaque', nargs='*', default=[], help='Names of backgrounds allowed to be opaque')
    p.add_argument('--wide', nargs='*', default=[], help='Names requiring at least 1280x720')
    p.add_argument('--expected', nargs='+', required=True, help='Complete required GIF filename list')
    a = p.parse_args()
    if len(set(a.expected)) != len(a.expected): p.error('duplicate filenames')
    if any(Path(n).name != n or not n.lower().endswith('.gif') for n in a.expected): p.error('expected names must be GIF basenames')
    for n in a.expected:
        size, count = inspect(a.directory / n, n in a.opaque, n in a.wide)
        print(f'{n}: {size[0]}x{size[1]}, {count} frames')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.output, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in a.expected: z.write(a.directory / n, n)

if __name__ == '__main__': main()
