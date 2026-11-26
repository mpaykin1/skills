#!/usr/bin/env python3
"""Pin and install original Shader-Stacker Godot 4 addon, MPL-2.0, in cache.

No editor scripts are rewritten. The caller may supply an existing verified addon tree
for strictly offline project generation.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

URL = 'https://github.com/x3cca/Shader-Stacker.git'
COMMIT = '21d86ab62140b0d08ea217982036e3cb184afed5'
CACHE = Path.home()/'.cache'/'meta-games'/'shader-stacker'/COMMIT


def valid_addon(path: Path) -> bool:
    required = ['plugin.cfg', 'init.gd', 'SpriteStack/SpriteStack.gd',
                'StackCamera/StackCamera.gd', 'Reset2D/Reset2D.gd',
                'SpriteStack/icon.svg', 'StackCamera/icon.svg', 'Reset2D/icon.svg']
    return path.is_dir() and all((path / x).is_file() for x in required)


def resolve(explicit: str|None = None, no_install: bool = False) -> tuple[Path,Path|None]:
    if explicit:
        root = Path(explicit).expanduser().resolve(strict=True)
        addon = root / 'addons' / 'ShaderStacker' if (root/'addons'/'ShaderStacker').is_dir() else root
        if not valid_addon(addon):
            raise ValueError('--addon must contain the official addons/ShaderStacker directory')
        license_path = root/'LICENSE' if (root/'LICENSE').is_file() else addon.parent.parent/'LICENSE'
        return addon, license_path if license_path.is_file() else None
    addon = CACHE/'addons'/'ShaderStacker'
    if valid_addon(addon) and (CACHE/'.git').is_dir():
        git = shutil.which('git')
        if git:
            p = subprocess.run([git, '-C', str(CACHE),'rev-parse','HEAD'],check=True,
                               capture_output=True,text=True,timeout=20)
            if p.stdout.strip() != COMMIT:
                raise RuntimeError('Cached Shader-Stacker revision mismatch')
        return addon, CACHE/'LICENSE'
    if no_install:
        raise RuntimeError('Pinned Shader-Stacker not cached: provide --addon or allow first git fetch')
    git = shutil.which('git')
    if not git:raise RuntimeError('git is needed for first Shader-Stacker install')
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    env = os.environ.copy();env['GIT_TERMINAL_PROMPT']='0'
    with tempfile.TemporaryDirectory(prefix='shader-stack-',dir=CACHE.parent) as tmp:
        repo = Path(tmp)/'source'
        commands = [
            [git,'init','-q',str(repo)],
            [git,'-C',str(repo),'remote','add','origin',URL],
            [git,'-C',str(repo),'fetch','--depth=1','origin',COMMIT],
            [git,'-C',str(repo),'checkout','--detach','FETCH_HEAD']
        ]
        for cmd in commands:
            subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=180,env=env)
        got = subprocess.run([git,'-C',str(repo),'rev-parse','HEAD'],check=True,
                             capture_output=True,text=True,timeout=20).stdout.strip()
        if got != COMMIT or not valid_addon(repo/'addons'/'ShaderStacker') or not (repo/'LICENSE').is_file():
            raise RuntimeError('Unexpected source structure or git commit')
        if CACHE.exists():
            raise RuntimeError('Existing incomplete cache; remove this unused cache folder manually and retry')
        repo.rename(CACHE)
    return addon, CACHE/'LICENSE'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--addon',help='Trusted existing official addon root, for offline builds')
    p.add_argument('--no-install',action='store_true')
    a=p.parse_args()
    addon,license_path=resolve(a.addon,a.no_install)
    print(addon)
    print('MPL-2.0 license:',license_path)

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError,subprocess.SubprocessError) as e:sys.exit('ERROR: '+str(e))
