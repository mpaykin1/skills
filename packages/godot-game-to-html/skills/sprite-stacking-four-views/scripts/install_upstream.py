#!/usr/bin/env python3
"""Fetch precisely pinned upstream Daniel White sprite-stacking slicer (MIT).

Source is installed into an isolated user cache only on first invocation.
No unchecked branches, no subprocess shell, no generated-looking substitute slices.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

UPSTREAM = 'https://github.com/danielwh2/sprite-stacking.git'
COMMIT = '0cce02efe6aa81fffcd05744d7ab65d40f412de2'
UPSTREAM_SCRIPT = Path('skills/sprite-stacking/scripts/views_to_slices.py')
CACHE = Path.home() / '.cache' / 'meta-games' / 'sprite-stacking-fourviews' / COMMIT


def resolve(explicit: str | None = None, *, no_install: bool = False) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix != '.py':
            raise ValueError('--upstream-script must point to the real views_to_slices.py')
        return path
    script = CACHE / UPSTREAM_SCRIPT
    if script.is_file() and (CACHE / '.git').is_dir():
        git = shutil.which('git')
        if git:
            revision = subprocess.run([git, '-C', str(CACHE), 'rev-parse', 'HEAD'],
                                      capture_output=True, text=True, timeout=20, check=True).stdout.strip()
            if revision != COMMIT:
                raise RuntimeError('Cached upstream revision changed; refusing to execute mismatched code')
        return script
    if no_install:
        raise RuntimeError('Pinned official sprite-stacking source not cached; rerun without --no-install-upstream')
    git = shutil.which('git')
    if not git:
        raise RuntimeError('git is required for first install of pinned open-source slicer')
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    with tempfile.TemporaryDirectory(prefix='sprite-stacking-fetch-', dir=CACHE.parent) as temp:
        root = Path(temp) / 'source'
        root.mkdir()
        commands = (
            [git, 'init', '-q', str(root)],
            [git, '-C', str(root), 'remote', 'add', 'origin', UPSTREAM],
            [git, '-C', str(root), 'fetch', '-q', '--depth=1', 'origin', COMMIT],
            [git, '-C', str(root), 'checkout', '-q', '--detach', 'FETCH_HEAD'],
        )
        for cmd in commands:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180, env=env)
        got = subprocess.run([git, '-C', str(root), 'rev-parse', 'HEAD'], check=True,
                             capture_output=True, text=True, timeout=20).stdout.strip()
        if got != COMMIT or not (root / UPSTREAM_SCRIPT).is_file():
            raise RuntimeError('Upstream git commit or source path does not match pinned version')
        if not CACHE.exists():
            root.rename(CACHE)
    if not script.is_file():
        raise RuntimeError('Pinned slicer did not install successfully')
    return script


def main() -> None:
    p = argparse.ArgumentParser(description='Install official pinned MIT sprite-stacking source into user cache')
    p.add_argument('--no-install', action='store_true')
    p.add_argument('--upstream-script', default=None)
    a = p.parse_args()
    print(resolve(a.upstream_script, no_install=a.no_install))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit('ERROR: ' + str(exc))
