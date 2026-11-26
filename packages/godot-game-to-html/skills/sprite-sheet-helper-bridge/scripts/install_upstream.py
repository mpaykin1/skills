#!/usr/bin/env python3
"""Pin and build the real Sprite Sheet Helper headless CLI (MIT) into a user cache."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

UPSTREAM = 'https://github.com/Kyonru/sprite-sheet-helper.git'
COMMIT = 'aacb362aa35e4fec8102f7d08e9955d65c03eb88'
CACHE = Path.home() / '.cache' / 'meta-games' / 'sprite-sheet-helper' / COMMIT


def executable(root: Path) -> Path:
    return root / 'dist' / 'cli' / 'index.js'


def resolve(explicit: str | None = None, no_install: bool = False) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve(strict=True)
        if not executable(root).is_file() or not (root / 'dist' / 'index.html').is_file():
            raise ValueError('--helper-root must be an already-built official Sprite Sheet Helper repository')
        return root
    git = shutil.which('git')
    if CACHE.is_dir():
        if git and (CACHE / '.git').is_dir():
            got = subprocess.run([git, '-C', str(CACHE), 'rev-parse', 'HEAD'],
                                 check=True, capture_output=True, text=True, timeout=30).stdout.strip()
            if got != COMMIT:
                raise RuntimeError('Sprite Sheet Helper cache was modified; pinned commit mismatch')
        if executable(CACHE).is_file() and (CACHE / 'dist' / 'index.html').is_file():
            return CACHE
        if no_install:
            raise RuntimeError('Pinned Sprite Sheet Helper is not built; install once without --no-install-helper')
    elif no_install:
        raise RuntimeError('Pinned Sprite Sheet Helper is not cached; install once without --no-install-helper')
    if not git:
        raise RuntimeError('git is needed to fetch pinned upstream source')
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('npm is needed for the official Vite + TypeScript CLI build')
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js is required for Sprite Sheet Helper')
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['CI'] = '1'
    with tempfile.TemporaryDirectory(prefix='ssh-build-', dir=CACHE.parent) as temporary:
        root = Path(temporary) / 'source'
        steps = [
            [git, 'init', '-q', str(root)],
            [git, '-C', str(root), 'remote', 'add', 'origin', UPSTREAM],
            [git, '-C', str(root), 'fetch', '-q', '--depth=1', 'origin', COMMIT],
            [git, '-C', str(root), 'checkout', '-q', '--detach', 'FETCH_HEAD'],
        ]
        for cmd in steps:
            subprocess.run(cmd, check=True, timeout=300, env=env, capture_output=True, text=True)
        got = subprocess.run([git, '-C', str(root), 'rev-parse', 'HEAD'],
                             check=True, capture_output=True, text=True, timeout=30).stdout.strip()
        if got != COMMIT:
            raise RuntimeError('Fetched upstream commit differs from pinned SHA')
        # The upstream CLI uses Puppeteer and a local Vite preview server.
        subprocess.run([npm, 'ci', '--no-audit', '--no-fund'], cwd=root, env=env, check=True, timeout=1200)
        subprocess.run([npm, 'run', 'build:cli'], cwd=root, env=env, check=True, timeout=900)
        if not executable(root).is_file() or not (root / 'dist' / 'index.html').is_file():
            raise RuntimeError('Upstream build: CLI or Vite browser assets missing')
        if CACHE.exists():
            # No mutation of a live cache/older release; keep the old folder intact.
            raise RuntimeError('Incomplete existing cache; delete only the incomplete cache manually')
        root.rename(CACHE)
    return CACHE


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--helper-root')
    p.add_argument('--no-install-helper', action='store_true')
    a = p.parse_args()
    print(resolve(a.helper_root, a.no_install_helper))


if __name__ == '__main__':
    try: main()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit('ERROR: ' + str(exc))
