#!/usr/bin/env python3
"""Acquire pinned CPU-only xatlas binding with user's Python interpreter."""
from __future__ import annotations
import argparse
import subprocess
import sys

VERSION='0.0.11'

def main():
    p=argparse.ArgumentParser(description='xatlas CPU install and preflight')
    p.add_argument('--python',default=sys.executable)
    p.add_argument('--install',action='store_true',help='Allow pip to download official xatlas and numpy wheels')
    a=p.parse_args()
    interpreter=a.python
    if a.install:
        subprocess.run([interpreter,'-m','pip','install',f'xatlas=={VERSION}','numpy'],check=True)
    snippet=("import xatlas,numpy,importlib.metadata as m; "
             "assert m.version('xatlas')=='0.0.11', 'Expected xatlas==0.0.11'; "
             "print('xatlas CPU ready:',m.version('xatlas'))")
    subprocess.run([interpreter,'-c',snippet],check=True)

if __name__=='__main__':main()
