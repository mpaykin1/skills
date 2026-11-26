#!/usr/bin/env python3
"""Download/check genuine Daniel White sprite-stacking source with pinned Git blob hashes.

Source is not impersonated by local fallback. Once installed it works offline.
MIT copyright and license are always preserved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

REPOSITORY = 'https://github.com/danielwh2/sprite-stacking'
BASE = 'https://raw.githubusercontent.com/danielwh2/sprite-stacking/main/'
# GitHub API blob SHA-1 values of the inspected upstream files, not guessed release tags.
FILES = {
    'skills/sprite-stacking/scripts/views_to_slices.py': '73972c1019988dcdb119bc8d9ba0ad55c0fcfd2d',
    'skills/sprite-stacking/scripts/viewer.html': '429e4b9cbd4413c586c3621ef7db694bbc514ab7',
    'skills/sprite-stacking/SKILL.md': 'fd9288455c3e2681816ddf86eaaeed3186e27f25',
    'LICENSE': 'f94c9b150dc7e0cbfcdf9f9d8bcff4aa79ca5688',
}

class UpstreamUnavailable(RuntimeError): pass

def git_blob_hash(data: bytes) -> str:
    return hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()

def verify(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    checked={}
    for relative,expected in FILES.items():
        f=root/relative
        if not f.is_file():
            raise UpstreamUnavailable(f'Genuine upstream file absent: {relative}; use --install-upstream once with network.')
        raw=f.read_bytes()
        digest=git_blob_hash(raw)
        if digest!=expected:
            raise UpstreamUnavailable(f'Upstream source has changed at {relative}; refusing unreviewed update (got {digest}).')
        checked[relative]={'git_blob_sha1':digest,'bytes':len(raw)}
    return {'source':REPOSITORY,'pinned_files':checked,'official_code_verified':True}

def install(root: Path, *, fetch: bool=False):
    root=Path(root).expanduser().resolve()
    if fetch:
        # Download bytes from the official source and verify BEFORE materializing.
        for relative,sha in FILES.items():
            dest=root/relative
            if dest.is_file() and git_blob_hash(dest.read_bytes())==sha:
                continue
            try:
                req=urllib.request.Request(BASE+relative,headers={'User-Agent':'Living-Image-Animator-danielwh2-integration/0.38'})
                with urllib.request.urlopen(req,timeout=30) as response:
                    data=response.read(3_000_000+1)
            except Exception as exc:
                raise UpstreamUnavailable('Original upstream download unavailable: '+str(exc)) from exc
            if len(data)>3_000_000 or git_blob_hash(data)!=sha:
                raise UpstreamUnavailable('Upstream changed or oversized at '+relative+'; refusing non-pinned code')
            dest.parent.mkdir(parents=True,exist_ok=True)
            tmp=dest.with_suffix(dest.suffix+'.download')
            tmp.write_bytes(data);tmp.replace(dest)
    info=verify(root)
    return root,info

def main():
    ap=argparse.ArgumentParser(description='Acquire or verify original danielwh2/sprite-stacking MIT CLI')
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--fetch',action='store_true')
    a=ap.parse_args()
    _,manifest=install(a.root,fetch=a.fetch)
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
