#!/usr/bin/env python3
"""Verify/install official Pillow 12.3.0 without CUDA or GPU.
Optional pinned upstream source checkout is separate from wheel installation.
"""
from __future__ import annotations
import argparse,importlib.metadata,subprocess,sys
from pathlib import Path

VERSION='12.3.0'
PIN='bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d'
REPO='https://github.com/python-pillow/Pillow.git'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--install',action='store_true')
    p.add_argument('--source-only',action='store_true')
    p.add_argument('--dest',default='vendor/Pillow-source')
    a=p.parse_args()
    if a.source_only:
        dst=Path(a.dest).expanduser().resolve()
        if dst.exists():p.error('Source destination already exists; do not overwrite')
        subprocess.run(['git','clone','--filter=blob:none',REPO,str(dst)],check=True)
        subprocess.run(['git','-C',str(dst),'checkout','--detach',PIN],check=True)
        return
    if a.install:
        subprocess.run([sys.executable,'-m','pip','install','--only-binary=:all:',
                       '--disable-pip-version-check','pillow=='+VERSION],check=True)
    version=importlib.metadata.version('Pillow')
    if version!=VERSION:raise RuntimeError(f'Pillow {version} installed, expected {VERSION}')
    from PIL import Image
    assert hasattr(Image,'frombytes')
    print('Pillow',version,'is usable on CPU. Upstream:',REPO,'commit:',PIN)

if __name__=='__main__':main()
