#!/usr/bin/env python3
"""Optional complete upstream Open Mocap checkout: pinned MIT source, no demo videos.

The compact skill already includes a CPU port of its pose-tracking math.
Downloading original Blender 4.0 addon is optional, only when explicitly needed.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess

REPO='https://github.com/Larenju-Rai/open-mocap-blender.git'
COMMIT='1ec7457dad228661cbd8a1d98163e8288d3f7db5'


def verify(path):
    if not (path/'utils.py').is_file() or not (path/'LICENSE.txt').is_file() or not (path/'__init__.py').is_file():
        raise RuntimeError('Not an actual Open Mocap source checkout')
    sha=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    if sha!=COMMIT:raise RuntimeError('Open Mocap checkout is not at pinned revision: '+sha)
    return sha


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dest',type=Path,default=Path('vendor/open-mocap-blender'))
    p.add_argument('--verify',action='store_true')
    a=p.parse_args();dest=a.dest.expanduser().resolve()
    if a.verify:
        print('Open Mocap verified',verify(dest));return
    if not shutil.which('git'):p.error('git executable missing')
    if not dest.exists():
        dest.mkdir(parents=True)
        subprocess.run(['git','-C',str(dest),'init','-q'],check=True)
        subprocess.run(['git','-C',str(dest),'remote','add','origin',REPO],check=True)
        subprocess.run(['git','-C',str(dest),'fetch','--depth','1','--filter=blob:none',
                        'origin',COMMIT],check=True)
        # No heavyweight copyrighted demo videos are needed for CPU capture.
        subprocess.run(['git','-C',str(dest),'config','core.sparseCheckout','true'],check=True)
        info=dest/'.git/info/sparse-checkout'
        info.parent.mkdir(parents=True,exist_ok=True)
        info.write_text('/utils.py\n/globalVariables.py\n/LICENSE.txt\n/README.md\n/__init__.py\n',encoding='utf8')
        subprocess.run(['git','-C',str(dest),'checkout','--detach',COMMIT],check=True)
    print('Open Mocap verified',verify(dest))

if __name__=='__main__':main()
