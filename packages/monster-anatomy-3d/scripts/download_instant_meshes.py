#!/usr/bin/env python3
"""Acquire/verify the exact open-source Instant Meshes revision and optional binary.

Pins upstream including five git submodules; aborts if repository is dirty or
incomplete. Instant Meshes is independent BSD-3-Clause-like source; reproduce
its LICENSE.txt with redistributions. No automatic binary execution.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = 'https://github.com/wjakob/instant-meshes.git'
COMMIT = '7b3160864a2e1025af498c84cfed91cbfb613698'
REQUIRED = ('LICENSE.txt', 'README.md', 'CMakeLists.txt', 'src/main.cpp',
            'src/batch.cpp', 'ext/nanogui', 'ext/tbb')

def call(args, *, cwd=None, timeout=1200):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    return subprocess.run([str(x) for x in args], cwd=cwd, env=env,
                          check=True, timeout=timeout, capture_output=True, text=True)

def inspect(dest: Path):
    if not (dest/'.git').exists():
        raise FileNotFoundError(f'Missing official Git checkout: {dest}')
    sha = call(['git','-C',dest,'rev-parse','HEAD']).stdout.strip()
    if sha != COMMIT: raise RuntimeError(f'Source commit differs: {sha} != {COMMIT}')
    missing=[str(f) for f in REQUIRED if not (dest/f).exists()]
    if missing: raise RuntimeError('Incomplete source: '+', '.join(missing))
    sub = call(['git','-C',dest,'submodule','status','--recursive']).stdout.splitlines()
    if not sub or any(s.startswith(('-', '+', 'U')) for s in sub):
        raise RuntimeError('Missing or inconsistent nested Git submodules')
    changed = call(['git','-C',dest,'status','--porcelain']).stdout.strip()
    if changed: raise RuntimeError('Source checkout modified; use a clean pinned checkout')
    return {'commit':sha,'path':str(dest),'submodules':len(sub)}

def fetch(dest: Path):
    dest=dest.resolve()
    if dest.exists() and any(dest.iterdir()): return inspect(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='instantmeshes_',dir=dest.parent) as td:
        src=Path(td)/'instant-meshes'
        try:
            call(['git','init',src]);call(['git','-C',src,'remote','add','origin',REPO])
            call(['git','-C',src,'fetch','--depth','1','origin',COMMIT])
            call(['git','-C',src,'checkout','--detach','FETCH_HEAD'])
            call(['git','-C',src,'submodule','update','--init','--recursive','--depth','1'])
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
            raise RuntimeError('Instant Meshes download failed: check DNS/network/submodules') from exc
        inspect(src)
        if dest.exists():dest.rmdir()
        shutil.move(str(src),str(dest))
    return inspect(dest)

def build(source: Path, build_dir: Path):
    inspect(source)
    build_dir=build_dir.resolve()
    try:
        call(['cmake','-S',source,'-B',build_dir,'-DCMAKE_BUILD_TYPE=Release'],timeout=1200)
        call(['cmake','--build',build_dir,'--config','Release','-j','4'],timeout=3600)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise RuntimeError('CMake build failed. Install C++ / OpenGL/GLFW dependencies and retry.') from exc
    candidates=list(build_dir.rglob('Instant Meshes'))+list(build_dir.rglob('Instant Meshes.exe'))
    candidates=[p for p in candidates if p.is_file()]
    if not candidates: raise RuntimeError('Built source but no Instant Meshes executable found')
    return str(candidates[0])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dest',default='vendor/instant-meshes')
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--build',action='store_true')
    ap.add_argument('--build-dir',default='')
    args=ap.parse_args()
    dest=Path(args.dest).expanduser().resolve()
    info=inspect(dest) if args.verify else fetch(dest)
    if args.build:
        info['binary']=build(dest,Path(args.build_dir).expanduser() if args.build_dir else dest.parent/'instant-meshes-build')
    print(json.dumps(info,indent=2))

if __name__=='__main__':main()
