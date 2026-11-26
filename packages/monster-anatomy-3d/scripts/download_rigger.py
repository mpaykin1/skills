#!/usr/bin/env python3
"""Download pinned official Rigger GPL-3.0 source, with strict verification.

This downloads an independent Blender addon, never embeds third-party source
inside our plugin. Run on a machine with Git and network access.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = 'https://github.com/asu37/Rigger.git'
COMMIT = 'c8f1d1b9a8729582c61fa0ffa9a658ec4f4f6e77'
REQUIRED = ('LICENSE','README.md','build.py','rigger/__init__.py',
            'rigger/quick_rig.py','rigger/retarget.py','rigger/export.py',
            'rigger/blender_manifest.toml')


def cmd(parts, *, timeout=240):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    return subprocess.run([str(x) for x in parts],capture_output=True,text=True,
                          check=True,timeout=timeout,env=env).stdout.strip()


def verify(dest:Path):
    if not (dest/'.git').is_dir():
        raise RuntimeError('Rigger source is not an official Git checkout: '+str(dest))
    sha=cmd(['git','-C',dest,'rev-parse','HEAD'])
    if sha!=COMMIT:raise RuntimeError(f'Incorrect upstream Rigger commit: {sha}; need {COMMIT}')
    absent=[p for p in REQUIRED if not (dest/p).is_file()]
    if absent:raise RuntimeError('Rigger checkout incomplete: '+', '.join(absent))
    dirty=cmd(['git','-C',dest,'status','--porcelain','--untracked-files=no'])
    if dirty:raise RuntimeError('Rigger tracked source files modified; stop for review')
    manifest=(dest/'rigger/blender_manifest.toml').read_text(encoding='utf-8')
    if 'GPL-3.0-or-later' not in manifest or 'blender_version_min = "4.2.0"' not in manifest:
        raise RuntimeError('Unexpected license or Blender requirements in checked-out upstream')
    return {'repository':REPO,'commit':sha,'path':str(dest),'source':'checked-out'}


def acquire(dest:Path):
    if dest.exists() and any(dest.iterdir()):return verify(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rigger-pinned-',dir=dest.parent) as tmp:
        checkout=Path(tmp)/'Rigger'
        try:
            cmd(['git','init',checkout]);cmd(['git','-C',checkout,'remote','add','origin',REPO])
            cmd(['git','-C',checkout,'fetch','--depth','1','origin',COMMIT],timeout=500)
            cmd(['git','-C',checkout,'checkout','--detach','FETCH_HEAD'])
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
            raise RuntimeError('Rigger checkout failed; verify network/DNS and Git availability') from exc
        data=verify(checkout)
        if dest.exists(): dest.rmdir()
        shutil.move(str(checkout),str(dest))
    return verify(dest)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dest',default='vendor/Rigger')
    p.add_argument('--verify',action='store_true',help='Never touch network')
    p.add_argument('--build-addon',action='store_true',help='Execute the upstream build.py to generate a Blender extension zip')
    args=p.parse_args();dest=Path(args.dest).expanduser().resolve()
    out=verify(dest) if args.verify else acquire(dest)
    if args.build_addon:
        import sys
        try:subprocess.run([sys.executable,str(dest/'build.py')],cwd=dest,check=True,timeout=200)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
            raise RuntimeError('Rigger build failed. Python and source dependencies are needed') from exc
        out['addon_archives']=[str(p) for p in (dest/'dist').glob('*.zip')]
        if not out['addon_archives']:raise RuntimeError('Rigger build finished without a zip')
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
