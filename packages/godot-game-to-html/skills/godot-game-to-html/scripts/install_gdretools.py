#!/usr/bin/env python3
"""Verified install of official GDRETools 2.7.4 CLI binaries (not redistributed in skill)."""
from __future__ import annotations
import argparse
import hashlib
import io
import os
from pathlib import Path
import platform
import stat
import sys
import urllib.request
import zipfile

VERSION = 'v2.7.4'
URL_BASE = 'https://github.com/GDRETools/gdsdecomp/releases/download/' + VERSION + '/'
# SHA-256 from the official GitHub release API, checked 2026-11-23.
SHA256 = {
    'linux': '3dc4f1244dda62e41e0c952ac00a69e60e07f3b0d5a211164806bf9d41a54758',
    'windows': 'af24c563eee501effb194d83595de64696c32547b2246034dbfb891a24bfa0ad',
    'macos': 'a148b9509c2826fcc238e81c21005bf3128bdcee1a87c3f79ad943a205aa2170',
}
MAX_ZIP_SIZE = 100 * 1024 * 1024
MAX_UNPACKED = 400 * 1024 * 1024


def run():
    ap = argparse.ArgumentParser(description='Install and verify upstream GDRETools release')
    ap.add_argument('--out', type=Path, default=Path.home()/'.cache'/'godot-game-to-html'/'gdretools'/VERSION)
    ap.add_argument('--archive', type=Path, help='Optional already-downloaded official ZIP, usable offline')
    a=ap.parse_args()
    os_name = platform.system().lower()
    if os_name.startswith('darwin'):
        os_name = 'macos'
    if os_name not in SHA256:
        raise RuntimeError('No pinned GDRETools build for this operating system')
    filename = f'GDRE_tools-{VERSION}-{os_name}.zip'
    if a.archive:
        data = a.archive.expanduser().read_bytes()
    else:
        url = URL_BASE+filename
        req=urllib.request.Request(url, headers={'User-Agent':'godot-game-to-html/1.1'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.geturl().split('/')[2].lower() not in ('github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):
                raise RuntimeError('Unexpected download host')
            data=resp.read(MAX_ZIP_SIZE+1)
    if len(data) > MAX_ZIP_SIZE:
        raise RuntimeError('Release ZIP too large')
    actual = hashlib.sha256(data).hexdigest()
    if actual != SHA256[os_name]:
        raise RuntimeError(f'GDRETools integrity mismatch: SHA-256 {actual} does not match pinned release')
    out = a.out.expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f'Install directory is not empty: {out}')
    with zipfile.ZipFile(io.BytesIO(data)) as zipf:
        members=zipf.infolist()
        if sum(i.file_size for i in members) > MAX_UNPACKED:
            raise RuntimeError('GDRETools archive has excessive uncompressed size')
        for info in members:
            name=info.filename
            path=(out/name).resolve()
            if not path.is_relative_to(out) or name.startswith(('/', '\\')):
                raise RuntimeError('Unsafe path in GDRETools archive')
            kind=(info.external_attr >> 16) & 0o170000
            if kind == stat.S_IFLNK:
                raise RuntimeError('Symlink in archive rejected')
        out.mkdir(parents=True, exist_ok=True)
        zipf.extractall(out)
    candidates=[]
    for p in out.rglob('*'):
        if not p.is_file():
            continue
        if 'gdre_tools' in p.name.lower() and (p.suffix == '.exe' or p.suffix == ''):
            if os.name != 'nt':
                p.chmod(p.stat().st_mode | stat.S_IXUSR)
            candidates.append(str(p.resolve()))
    if not candidates:
        raise RuntimeError('Archive installed, but GDRETools executable not recognized')
    print('Installed official GDRETools '+VERSION+':')
    for c in candidates:
        print(c)


if __name__=='__main__':
    try:
        run()
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as e:
        sys.exit('ERROR: '+str(e))
