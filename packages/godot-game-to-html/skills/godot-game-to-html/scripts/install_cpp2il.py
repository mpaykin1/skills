#!/usr/bin/env python3
"""Build the pinned official Cpp2IL development CLI locally with .NET 10.

No binary redistribution. Builds only when explicitly requested. Official MIT source:
https://github.com/SamboyCoding/Cpp2IL . Pin the commit for reproducibility.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

COMMIT = "b5ad444b82267cb1e4b88b8b373c008105bdea52"  # verified 2026-11-23
ROOT = Path.home()/'.cache'/'godot-unity-to-html'/'cpp2il'/COMMIT
REPO = 'https://github.com/SamboyCoding/Cpp2IL.git'


def tool_path():
    return ROOT/'bin'/('Cpp2IL.exe' if os.name == 'nt' else 'Cpp2IL')


def resolve(explicit: str | None = None, *, install: bool = False) -> str:
    if explicit:
        candidate = Path(explicit).expanduser().resolve(strict=True)
        if not candidate.is_file(): raise ValueError('Cpp2IL executable not a file: '+str(candidate))
        return str(candidate)
    env = os.environ.get('CPP2IL_EXE')
    if env: return resolve(env)
    path = tool_path()
    if path.is_file(): return str(path)
    exe = shutil.which('Cpp2IL') or shutil.which('cpp2il') or shutil.which('Cpp2IL-Win')
    if exe: return exe
    if install: return build_pinned()
    raise RuntimeError('Cpp2IL missing. Supply --cpp2il /path/to/Cpp2IL, set CPP2IL_EXE, or explicitly run install_cpp2il.py (git + .NET SDK 10 required)')


def build_pinned() -> str:
    existing = tool_path()
    if existing.is_file(): return str(existing)
    git = shutil.which('git')
    dotnet = shutil.which('dotnet')
    if not git or not dotnet:
        raise RuntimeError('Pinned Cpp2IL build requires git and .NET SDK 10; existing Cpp2IL can be provided with --cpp2il')
    probe = subprocess.run([dotnet,'--version'],capture_output=True,text=True,timeout=30,check=True)
    if int(probe.stdout.split('.',1)[0]) < 10:
        raise RuntimeError('Current Cpp2IL development CLI requires .NET SDK 10; found '+probe.stdout.strip())
    src = ROOT/'source'
    dest = ROOT/'bin'
    ROOT.mkdir(parents=True,exist_ok=True)
    if not (src/'.git').is_dir():
        if src.exists() and any(src.iterdir()): raise RuntimeError('Unexpected nonempty source directory: '+str(src))
        src.mkdir(parents=True,exist_ok=True)
        subprocess.run([git,'init','-q',str(src)],check=True,timeout=30)
        subprocess.run([git,'-C',str(src),'remote','add','origin',REPO],check=True,timeout=30)
        subprocess.run([git,'-C',str(src),'fetch','-q','--depth','1','origin',COMMIT],check=True,timeout=600)
        subprocess.run([git,'-C',str(src),'checkout','-q','--detach','FETCH_HEAD'],check=True,timeout=60)
    rev=subprocess.run([git,'-C',str(src),'rev-parse','HEAD'],capture_output=True,text=True,check=True,timeout=30).stdout.strip()
    if rev!=COMMIT: raise RuntimeError('Source commit differs from pin; refusing build: '+rev)
    dest.mkdir(parents=True,exist_ok=True)
    project=src/'Cpp2IL'/'Cpp2IL.csproj'
    subprocess.run([dotnet,'publish',str(project),'-f','net10.0','-c','Release','--self-contained','false','-p:PublishTrimmed=false','-o',str(dest)],check=True,timeout=1800)
    if not existing.is_file(): raise RuntimeError('Cpp2IL publish did not produce executable at '+str(existing))
    return str(existing)


def main():
    parser=argparse.ArgumentParser(description='Locate or build pinned official MIT Cpp2IL from source')
    parser.add_argument('--check',action='store_true',help='Only locate already installed Cpp2IL')
    args=parser.parse_args()
    print(resolve(install=not args.check))

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as e:sys.exit('ERROR: '+str(e))
