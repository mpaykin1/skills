#!/usr/bin/env python3
"""Download and verify pinned official Microsoft TRELLIS.2 source + submodules.

Weights are NOT bundled or automatically installed. Use the official setup.sh
and Hugging Face checkpoint on a Linux CUDA workstation. Never execute
unverified downloaded code automatically.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = 'https://github.com/microsoft/TRELLIS.2.git'
COMMIT = '75fbf0183001ed9876c8dbb35de6b68552ee08bd'
REQUIRED = ('README.md', 'LICENSE', 'setup.sh', 'example.py',
            'trellis2/pipelines/trellis2_image_to_3d.py', 'o-voxel')


def invoke(cmd, *, cwd=None):
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1', GIT_TERMINAL_PROMPT='0')
    subprocess.run(list(map(str,cmd)), cwd=cwd, env=env, check=True, timeout=1200)


def inspect_source(dest:Path):
    if not (dest/'.git').is_dir():
        raise FileNotFoundError(f'Official TRELLIS.2 git checkout absent: {dest}')
    got = subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'], text=True).strip()
    if got != COMMIT:
        raise RuntimeError(f'Unexpected TRELLIS.2 source commit {got}; require {COMMIT}')
    missing=[str(f) for f in REQUIRED if not (dest/f).exists()]
    if missing: raise RuntimeError('Incomplete TRELLIS.2 source: '+', '.join(missing))
    sub = subprocess.check_output(['git','-C',str(dest),'submodule','status','--recursive'],text=True).splitlines()
    if any(x.startswith(('-', '+', 'U')) for x in sub):
        raise RuntimeError('TRELLIS.2 submodules not initialized at required commits')
    return {'repo':REPO,'commit':got,'checkout':str(dest),'submodules':len(sub)}


def fetch(dest:Path):
    dest=dest.expanduser().resolve()
    if dest.exists() and any(dest.iterdir()): return inspect_source(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='trellis2_fetch_',dir=str(dest.parent)) as d:
        work=Path(d)/'TRELLIS.2'
        try:
            invoke(['git','init',str(work)])
            invoke(['git','-C',str(work),'remote','add','origin',REPO])
            invoke(['git','-C',str(work),'fetch','--depth','1','origin',COMMIT])
            invoke(['git','-C',str(work),'checkout','--detach','FETCH_HEAD'])
            invoke(['git','-C',str(work),'submodule','update','--init','--recursive','--depth','1'])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError('Unable to download TRELLIS.2 source. Check network/DNS and GitLab submodules.') from exc
        inspect_source(work)
        if dest.exists():dest.rmdir()
        shutil.move(str(work),str(dest))
    return inspect_source(dest)


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--dest',default='vendor/TRELLIS.2')
    a.add_argument('--verify',action='store_true')
    opt=a.parse_args()
    dest=Path(opt.dest)
    print(json.dumps(inspect_source(dest) if opt.verify else fetch(dest),indent=2))
    print('Only source is obtained. Model weights and CUDA dependencies must be installed separately.')

if __name__=='__main__':main()
