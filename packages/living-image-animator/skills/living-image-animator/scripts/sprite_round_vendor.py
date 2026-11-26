#!/usr/bin/env python3
"""Pin genuine SoAp9035/sprite-in-the-round MIT sources at a reviewed commit.

No substitute implementations; prepare an authentic upstream offline CLI install
at build time. Neither game nor preview does a network request at runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO='https://github.com/SoAp9035/sprite-in-the-round.git'
COMMIT='1d842b4d6d4e7f26b13236dedaf5841ecbfec267'
REQUIRED=('scripts/stack.py','scripts/voxlib.py','scripts/glb.py','assets/viewer.html','LICENSE')
class UpstreamUnavailable(RuntimeError):pass


def check(location: Path):
    root=Path(location).expanduser().resolve()
    for name in REQUIRED:
        file=root/name
        if not file.is_file() or file.stat().st_size < (4000 if name.endswith(('.py','.html')) else 500):
            raise UpstreamUnavailable('Original sprite-in-the-round source missing or truncated: '+str(file))
    license_text=(root/'LICENSE').read_text('utf8')
    if 'MIT License' not in license_text or 'Ahmet Burhan' not in license_text:
        raise UpstreamUnavailable('Original upstream MIT license missing or changed')
    if not (root/'scripts/stack.py').read_text('utf8').count('def main():')==1:
        raise UpstreamUnavailable('Upstream stack.py export entrypoint missing')
    head=(root/'scripts/glb.py').read_text('utf8')
    if 'def write_glb(' not in head or 'def write_obj(' not in head:
        raise UpstreamUnavailable('Original GLB and OBJ export code absent')
    return root


def fetch(destination:Path, git='git'):
    exe=shutil.which(git)
    if exe is None:raise UpstreamUnavailable('Genuine git required to fetch pinned sprite-in-the-round source')
    destination=Path(destination).expanduser().resolve()
    if destination.exists():raise UpstreamUnavailable('Destination already exists; do not overwrite other sourced code')
    with tempfile.TemporaryDirectory(prefix='lia_sprite_round_') as tmp:
        root=Path(tmp)/'repository'
        def run(cmd):
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=180,check=False)
            if p.returncode:raise UpstreamUnavailable('Upstream git operation failed: '+(p.stderr or p.stdout)[-700:])
            return p.stdout.strip()
        run([exe,'clone','--quiet','--no-checkout',REPO,str(root)])
        run([exe,'-C',str(root),'checkout','--quiet','--detach',COMMIT])
        if run([exe,'-C',str(root),'rev-parse','HEAD'])!=COMMIT:
            raise UpstreamUnavailable('Upstream git commit differs from pinned release')
        check(root)
        destination.mkdir(parents=True,exist_ok=False)
        for path in REQUIRED:
            target=destination/path;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(root/path,target)
        (destination/'UPSTREAM_COMMIT.txt').write_text(COMMIT+'\n'+REPO+'\n','utf8')
    return check(destination)


def locate(path:Path|None=None):
    target=path or os.environ.get('LIA_SPRITE_IN_THE_ROUND') or Path(__file__).resolve().parents[3]/'vendor'/'sprite-in-the-round'
    return check(Path(target))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True,type=Path);p.add_argument('--git',default='git')
    a=p.parse_args();print(fetch(a.out,a.git))
