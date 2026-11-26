#!/usr/bin/env python3
"""Pinned real MIT xatlas + Python-binding source checkout (network required)."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

PYTHON_REPO='https://github.com/mworchel/xatlas-python.git'
PYTHON_REV='64bbecad2db3e01767d28f8ad6f41f6fbdb04db3'


def run(*args,cwd=None):
    subprocess.run(['git',*map(str,args)],cwd=cwd,check=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dest',default='vendor/xatlas-python')
    p.add_argument('--verify',action='store_true',help='Offline validation of existing checked-out code')
    a=p.parse_args();dest=Path(a.dest).expanduser().resolve()
    if not a.verify and not (dest/'.git').exists():
        dest.parent.mkdir(parents=True,exist_ok=True)
        run('clone','--recurse-submodules',PYTHON_REPO,dest)
    if not (dest/'.git').exists():
        p.error('Official xatlas-python checkout missing; network needed to download')
    if not a.verify:
        run('fetch','origin',PYTHON_REV,cwd=dest)
        run('checkout','--detach',PYTHON_REV,cwd=dest)
        run('submodule','update','--init','--recursive',cwd=dest)
    result=subprocess.run(['git','rev-parse','HEAD'],cwd=dest,capture_output=True,text=True,check=True)
    if result.stdout.strip()!=PYTHON_REV:
        p.error('xatlas source commit pin mismatch')
    if not (dest/'LICENSE').is_file() or not (dest/'pyproject.toml').is_file():
        p.error('Source is missing required MIT license or package manifest')
    print('Verified official xatlas Python binding source:',dest)

if __name__=='__main__':main()
