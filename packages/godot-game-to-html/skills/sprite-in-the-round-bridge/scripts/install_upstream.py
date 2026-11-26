#!/usr/bin/env python3
"""Resolve the real sprite-in-the-round open-source implementation at a pinned commit.

MIT © 2026 Ahmet Burhan Kayalı. No vendored binaries, code substitution or branch drift.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

UPSTREAM = 'https://github.com/SoAp9035/sprite-in-the-round.git'
COMMIT = '1d842b4d6d4e7f26b13236dedaf5841ecbfec267'
CACHE = Path.home()/'.cache'/'meta-games'/'sprite-in-the-round'/COMMIT
REQUIRED = ['scripts/stack.py', 'scripts/glb.py', 'scripts/voxlib.py', 'assets/viewer.html', 'LICENSE']


def check(root: Path) -> Path:
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Upstream root is not a directory')
    for relative in REQUIRED:
        f = root/relative
        if f.is_symlink() or not f.is_file() or root not in f.resolve().parents:
            raise ValueError('Incomplete official sprite-in-the-round tree: '+relative)
    return root


def resolve(root: str|None = None, *, no_install: bool = False) -> Path:
    if root:
        return check(Path(root))
    if CACHE.exists():
        if not (CACHE/'.git').is_dir():
            raise RuntimeError('Existing cache has no git provenance; refuse running unverified code')
        git = shutil.which('git')
        if not git:
            raise RuntimeError('git required to verify pinned source revision')
        revision = subprocess.run([git,'-C',str(CACHE),'rev-parse','HEAD'],
                                  check=True,capture_output=True,text=True,timeout=25).stdout.strip()
        if revision != COMMIT:
            raise RuntimeError('Cached upstream HEAD changed; pinned revision mismatch')
        return check(CACHE)
    if no_install:
        raise RuntimeError('Pinned sprite-in-the-round source absent; install first or supply --upstream-root')
    git = shutil.which('git')
    if not git:
        raise RuntimeError('git required to obtain pinned official source')
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    env = os.environ.copy(); env['GIT_TERMINAL_PROMPT'] = '0'
    with tempfile.TemporaryDirectory(dir=CACHE.parent,prefix='sprite-round-') as tmp:
        work = Path(tmp)/'source'; work.mkdir()
        commands = ([git,'init','-q',str(work)],
                    [git,'-C',str(work),'remote','add','origin',UPSTREAM],
                    [git,'-C',str(work),'fetch','-q','--depth=1','origin',COMMIT],
                    [git,'-C',str(work),'checkout','-q','--detach','FETCH_HEAD'])
        for cmd in commands:
            subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=240,env=env)
        rev = subprocess.run([git,'-C',str(work),'rev-parse','HEAD'],
                             check=True,capture_output=True,text=True,timeout=25).stdout.strip()
        if rev != COMMIT:
            raise RuntimeError('Official repository revision mismatch')
        check(work)
        if CACHE.exists():
            return resolve(no_install=True)
        work.rename(CACHE)
    return check(CACHE)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream-root')
    p.add_argument('--no-install',action='store_true')
    a=p.parse_args(); print(resolve(a.upstream_root,no_install=a.no_install))

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as err:
        sys.exit('ERROR: '+str(err))
