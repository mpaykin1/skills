#!/usr/bin/env python3
"""Install a pinned MIT UnityPy into an isolated Python venv (no vendored binaries)."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import venv

VERSION='1.25.4'

def install(dest: Path) -> Path:
    dest=dest.expanduser().resolve()
    exe=dest/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if not exe.is_file():
        dest.parent.mkdir(parents=True,exist_ok=True)
        venv.EnvBuilder(with_pip=True,clear=False).create(dest)
    cmd=[str(exe),'-m','pip','install','--disable-pip-version-check','--only-binary=:all:',f'UnityPy=={VERSION}']
    subprocess.run(cmd,check=True,timeout=900)
    subprocess.run([str(exe),'-c',f'import UnityPy; assert UnityPy.__version__ == "{VERSION}"'],check=True,timeout=60)
    return exe

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,default=Path.home()/'.cache'/'godot-unity-to-html'/'unitypy'/VERSION)
    args=ap.parse_args()
    print(install(args.out))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:sys.exit('ERROR: '+str(e))
