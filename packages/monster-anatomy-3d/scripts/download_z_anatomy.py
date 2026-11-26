#!/usr/bin/env python3
"""Download an upstream, pinned Z-Anatomy Blender application template.

No Z-Anatomy models are bundled into the plugin. Model sources are not
implicitly licensed for commercial distribution: inspect individual assets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request

OWNER_REPO = 'Z-Anatomy/Models-of-human-anatomy'
COMMIT = 'd14fa54355a3b484cefd08c33f6e18526d9aea85'
FILES = {
    'Z-Anatomy.zip': ('f43cabc6f366b2a6058dd2ed4a2b3c7b9b2492cb', 86734957),
    'License.txt': ('4d48d7e83d2b79ba4510314c7612b2c3c0a90f67', 2754),
    'Readme.md': ('230bc88d7699453c46133bef75c8e8c14d1b9574', 4243),
    'Z-Biomechanics.7z': ('0a59584deaf21773ffa3acb063f2cd06f3485a98', 21644942),
}

def fetch(name: str, target: Path, timeout: int = 120) -> dict:
    expected, expected_bytes = FILES[name]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == expected_bytes:
        data = target.read_bytes()
        digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if digest == expected:
            return {'path': str(target), 'size':len(data), 'git_blob_sha1':digest, 'cached': True}
    url = f'https://raw.githubusercontent.com/{OWNER_REPO}/{COMMIT}/{name}'
    req = urllib.request.Request(url, headers={'User-Agent':'Monster-Anatomy-3D/0.2 (source download)'})
    temp = target.with_name(target.name + '.part')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(temp, 'wb') as out:
            written = 0
            while True:
                piece = r.read(1024 * 512)
                if not piece: break
                written += len(piece)
                if written > expected_bytes: raise ValueError('Unexpected upstream file size')
                out.write(piece)
        if written != expected_bytes: raise ValueError(f'File size mismatch {written} != {expected_bytes}')
        # Git blob object hash verification, not only the compressed zip header.
        h = hashlib.sha1()
        h.update(b'blob ' + str(written).encode() + b'\0')
        with open(temp, 'rb') as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b''): h.update(chunk)
        if h.hexdigest() != expected:
            raise ValueError('Git object SHA mismatch; upstream file changed or download corrupt')
        os.replace(temp, target)
        return {'path':str(target), 'size':written, 'git_blob_sha1':expected, 'cached':False}
    finally:
        temp.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dest', default='vendor/Z-Anatomy')
    p.add_argument('--with-biomechanics', action='store_true')
    args=p.parse_args()
    names=['License.txt','Readme.md','Z-Anatomy.zip']
    if args.with_biomechanics: names.append('Z-Biomechanics.7z')
    results=[]
    for name in names:
        print('Fetching:',name,flush=True)
        results.append(fetch(name, Path(args.dest)/name))
    (Path(args.dest)/'SOURCE.json').write_text(json.dumps({
       'repo':OWNER_REPO,'commit':COMMIT,'files':results,
       'copyright':'Upstream copyright remains with respective rightsholders',
       'license_notice':'CC BY-SA 4.0 for original atlas; per-object exclusions include CC BY-NC variants. Not automatically cleared for commercial games.'
    },indent=2),encoding='utf8')
    print('Z-Anatomy template source ready:',str(Path(args.dest).resolve()))

if __name__=='__main__':main()
