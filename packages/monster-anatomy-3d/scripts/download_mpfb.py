#!/usr/bin/env python3
"""Fetch pinned official MPFB 2 source via GitHub, then extract its Blender add-on.

A fetch/install helper, not a replacement for MPFB. It does not execute any
third-party code. Requires network access; offline --verify only checks presence.
Source code remains GPL-3.0-or-later. MPFB bundled art assets are CC0.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

REPO = 'makehumancommunity/mpfb2'
COMMIT = '9de0707fdc88438d7c53a1a2ac7937d9221e2431'
SOURCE_URL = f'https://codeload.github.com/{REPO}/zip/{COMMIT}'
MAX_DOWNLOAD = 250 * 1024 * 1024
MAX_EXTRACT = 700 * 1024 * 1024
REQUIRED = (
    'src/mpfb/blender_manifest.toml',
    'src/mpfb/__init__.py',
    'src/mpfb/services/humanservice.py',
    'src/mpfb/services/targetservice.py',
    'src/mpfb/data/rigs/standard/rig.game_engine.json',
    'LICENSE.md',
    'LICENSE.CODE.md',
    'LICENSE.ASSETS.md',
)

def check_source(destination: Path) -> dict:
    missing = [name for name in REQUIRED if not (destination / name).is_file()]
    if missing:
        raise FileNotFoundError('MPFB source missing: ' + ', '.join(missing) + '. Run without --verify on a network-connected machine.')
    meta = destination / 'SOURCE.json'
    if not meta.is_file() or json.loads(meta.read_text(encoding='utf8')).get('commit') != COMMIT:
        raise ValueError('MPFB source version could not be verified against pinned commit')
    return {'source': REPO, 'commit': COMMIT, 'path': str(destination.resolve())}

def fetch_source(destination: Path) -> dict:
    if destination.exists():
        # Never delete user data when a destination is an unknown directory.
        if any(destination.iterdir()):
            return check_source(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='monster_mpfb_', dir=str(destination.parent)) as tempdir:
        temp = Path(tempdir)
        archive = temp / 'MPFB.zip'
        request = urllib.request.Request(SOURCE_URL, headers={'User-Agent': 'Monster-Anatomy-3D/0.3 source downloader'})
        count = 0
        with urllib.request.urlopen(request, timeout=120) as response, archive.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                count += len(chunk)
                if count > MAX_DOWNLOAD: raise ValueError('MPFB source archive exceeds configured limit')
                output.write(chunk)
        extracted = temp / 'src'; extracted.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            paths = {}
            for entry in bundle.infolist():
                if entry.is_dir(): continue
                name = entry.filename.replace('\\', '/')
                parts = name.split('/')
                if len(parts) < 2 or any(part in ('', '..', '.') for part in parts):
                    raise ValueError('Unexpected ZIP member path')
                rel = '/'.join(parts[1:])
                # Repository assets may include tarballs; preserve official MPFB source only.
                if not (rel.startswith('src/mpfb/') or rel in REQUIRED or rel.startswith('script_samples/')):
                    continue
                paths[rel] = entry
            missing = [path for path in REQUIRED if path not in paths]
            if missing: raise ValueError('Unexpected upstream layout; missing: ' + ', '.join(missing))
            total = sum(item.file_size for item in paths.values())
            if total > MAX_EXTRACT: raise ValueError('Uncompressed source exceeds limit')
            for rel, entry in paths.items():
                to = extracted / rel
                to.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(entry) as source, to.open('wb') as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
        (extracted / 'SOURCE.json').write_text(json.dumps({
            'repository': f'https://github.com/{REPO}',
            'commit': COMMIT,
            'archive_url': SOURCE_URL,
            'code_license': 'GPL-3.0-or-later',
            'bundled_assets_license': 'CC0-1.0',
            'warning': 'Additional third-party installed assets may use different licenses',
        }, indent=2), encoding='utf8')
        if destination.exists():
            if any(destination.iterdir()):
                raise FileExistsError('Destination became non-empty; refusing to overwrite')
            destination.rmdir()
        extracted.rename(destination)
    return check_source(destination)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dest', default='vendor/MPFB2')
    p.add_argument('--verify', action='store_true', help='Check pinned source exists; do not connect to the network')
    args = p.parse_args()
    path = Path(args.dest).expanduser().resolve()
    print(json.dumps(check_source(path) if args.verify else fetch_source(path), indent=2))
    print('MPFB source downloaded. Activate its Blender add-on before generating a donor; source alone is not installed.')

if __name__ == '__main__': main()
