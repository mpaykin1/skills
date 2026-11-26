#!/usr/bin/env python3
"""Install AssetRipper 2.0.0 from upstream GitHub release (GPLv3, NOT bundled).

Full release SHA-256 pins were read from AssetRipper's GitHub release API.
CPU only. Preserves downstream GPL obligations when redistributing the program.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import os
from pathlib import Path
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile

VERSION = '2.0.0'
ROOT = 'https://github.com/AssetRipper/AssetRipper/releases/download/' + VERSION + '/'
ASSETS = {
    ('Linux','x86_64'): ('AssetRipper_linux_x64.tar.xz', '6f5d4352d36795b944243eb3ec790ec37dbca6d6756e52605bc8616e042d384e'),
    ('Linux','aarch64'): ('AssetRipper_linux_arm64.tar.xz', '8031752621d7fb27addab6108bad8bfbd43546bbb07b36912a987dfb4029c914'),
    ('Darwin','x86_64'): ('AssetRipper_mac_x64.tar.xz', '1b3836f135d16845cb57595fadff5739cbb86d28caaf621005b4301dba9b5a56'),
    ('Darwin','arm64'): ('AssetRipper_mac_arm64.tar.xz', '237a6da404bf089c5e5c71a5a9a698c2ea580872292dfa5ce21e25fd1dbe9045'),
    ('Windows','AMD64'): ('AssetRipper_win_x64.zip', '9a7ef0e7c5c3ea5b90b4e6d855e2d98d5f7ec8c3f9e26fccbc194c6a7b01baf7'),
    ('Windows','ARM64'): ('AssetRipper_win_arm64.zip', 'c2c3a335948aa0ecaf26baf22ac77e36993d1a1695b5db291cb63f66872627f1'),
}
MAX_DOWNLOAD = 90 * 1024 * 1024
MAX_UNPACKED = 800 * 1024 * 1024


def asset_for_system():
    arch=platform.machine()
    sysname=platform.system()
    if arch in {'amd64','x64'}: arch='AMD64' if sysname=='Windows' else 'x86_64'
    if arch=='arm64' and sysname=='Linux': arch='aarch64'
    if arch=='aarch64' and sysname=='Darwin': arch='arm64'
    key=(sysname,arch)
    if key not in ASSETS:
        raise RuntimeError(f'No pinned official AssetRipper build for {key}')
    return ASSETS[key]


def safe_destination(root:Path,name:str):
    p=(root/name).resolve()
    if name.startswith(('/', '\\')) or not p.is_relative_to(root):
        raise ValueError('Unsafe archive path: '+name)
    return p


def install(data:bytes, filename:str, out:Path):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Install folder is not empty: '+str(out))
    if filename.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            files=z.infolist()
            if sum(x.file_size for x in files)>MAX_UNPACKED: raise ValueError('Archive expands beyond limit')
            for e in files:
                safe_destination(out,e.filename)
                if (e.external_attr >> 16) & 0o170000 == stat.S_IFLNK: raise ValueError('Symlink rejected')
            for e in files:
                p=safe_destination(out,e.filename)
                if e.is_dir(): p.mkdir(parents=True,exist_ok=True)
                else:
                    p.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(e) as src, p.open('wb') as dest:
                        import shutil; shutil.copyfileobj(src,dest)
    else:
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as tar:
            files=tar.getmembers()
            if sum(x.size for x in files)>MAX_UNPACKED: raise ValueError('Archive expands beyond limit')
            for e in files:
                safe_destination(out,e.name)
                if not (e.isdir() or e.isfile()): raise ValueError('Nonregular tar member rejected')
            for e in files:
                p=safe_destination(out,e.name)
                if e.isdir(): p.mkdir(parents=True,exist_ok=True)
                else:
                    p.parent.mkdir(parents=True,exist_ok=True)
                    source=tar.extractfile(e)
                    if source is None: raise ValueError('Missing file content')
                    with source, p.open('wb') as dest:
                        import shutil; shutil.copyfileobj(source,dest)
                    if e.mode & 0o111: p.chmod(p.stat().st_mode|stat.S_IXUSR)
    candidates=[p for p in out.rglob('*') if p.is_file() and p.name.lower() in ('assetripper','assetripper.exe')]
    if not candidates: raise ValueError('Missing AssetRipper executable in official archive')
    for p in candidates:
        if os.name!='nt':p.chmod(p.stat().st_mode|stat.S_IXUSR)
    return candidates


def main():
    ap=argparse.ArgumentParser(description='Install verified upstream AssetRipper (GPL-3.0)')
    ap.add_argument('--out',type=Path,default=Path.home()/'.cache'/'godot-unity-to-html'/'assetripper'/VERSION)
    ap.add_argument('--archive',type=Path,help='Already-downloaded official archive; offline mode')
    a=ap.parse_args()
    filename,expected=asset_for_system()
    if a.archive: data=a.archive.expanduser().read_bytes()
    else:
        req=urllib.request.Request(ROOT+filename,headers={'User-Agent':'GodotUnityToHTML/1.2'})
        with urllib.request.urlopen(req,timeout=180) as resp:
            if resp.geturl().split('/')[2].lower() not in ('github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):
                raise ValueError('Unexpected release download host')
            data=resp.read(MAX_DOWNLOAD+1)
    if len(data)>MAX_DOWNLOAD: raise ValueError('Official release archive exceeded size limit')
    if hashlib.sha256(data).hexdigest()!=expected: raise ValueError('Official AssetRipper SHA-256 mismatch')
    out=a.out.expanduser().resolve()
    for exe in install(data,filename,out): print(exe)

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,tarfile.TarError,zipfile.BadZipFile) as e:sys.exit('ERROR: '+str(e))
