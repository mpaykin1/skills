#!/usr/bin/env python3
"""Fetch a pinned official Blender LTS binary or source with upstream SHA-256.

The Blender runtime is an external application, not embedded in the plugin ZIP.
On Linux x64 and Windows x64 this helper downloads the official standalone
archive and verifies it using the official Blender checksums file.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile

VERSION = '4.5.16'
RELEASE = 'https://download.blender.org/release/Blender4.5/'
SOURCE = 'https://projects.blender.org/blender/blender.git'
SOURCE_TAG = 'v4.5.16'
SOURCE_COMMIT = '3f6797307da591fd6feb47013bd117ec557931a7'
FILES = {
    'linux-x64': f'blender-{VERSION}-linux-x64.tar.xz',
    'windows-x64': f'blender-{VERSION}-windows-x64.zip',
}

def host_platform():
    mach = platform.machine().lower()
    if mach not in ('x86_64', 'amd64'):
        raise RuntimeError('Official portable installer currently supports x64 hosts only; install Blender manually and pass --blender')
    if sys.platform.startswith('linux'): return 'linux-x64'
    if sys.platform == 'win32': return 'windows-x64'
    raise RuntimeError('On macOS install the official Blender 4.5.16 package and pass its executable with --blender')

def get(url, path, limit):
    req=urllib.request.Request(url,headers={'User-Agent':'MonsterAnatomy3D/0.4.0'})
    with urllib.request.urlopen(req, timeout=35) as inp, path.open('wb') as out:
        size=0
        while True:
            buf=inp.read(1024*1024)
            if not buf:break
            size+=len(buf)
            if size > limit:raise RuntimeError('Upstream download exceeded allowed size')
            out.write(buf)
    if size<4096: raise RuntimeError('Unexpectedly small archive response: '+url)

def load_checksums(path):
    expected={}
    for line in path.read_text('utf8').splitlines():
        fields=line.split()
        if len(fields)<2 or len(fields[0])!=64: continue
        name=fields[-1].lstrip('*').split('/')[-1]
        expected[name]=fields[0].lower()
    if not expected:raise RuntimeError('Official SHA256 manifest is unreadable')
    return expected

def verify(src, expected):
    d=hashlib.sha256()
    with src.open('rb') as inp:
        for chunk in iter(lambda:inp.read(1024*1024),b''): d.update(chunk)
    if d.hexdigest().lower()!=expected.lower():raise RuntimeError('SHA-256 mismatch: '+src.name)

def safe_extract(archive, dest, format):
    dest.mkdir(parents=True,exist_ok=True)
    base=dest.resolve()
    if format=='zip':
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                target=(dest/item.filename).resolve()
                if not target.is_relative_to(base): raise RuntimeError('Unsafe ZIP path')
                if item.file_size>1024*1024*1024: raise RuntimeError('Unexpected ZIP entry size')
            z.extractall(dest)
    else:
        with tarfile.open(archive,'r:xz') as tar:
            for item in tar:
                if not item.isfile() and not item.isdir():raise RuntimeError('Unexpected source archive link/device')
                target=(dest/item.name).resolve()
                if not target.is_relative_to(base):raise RuntimeError('Unsafe TAR path')
                if item.size>1024*1024*1024: raise RuntimeError('Unexpected TAR entry size')
                if item.isdir():target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with tar.extractfile(item) as src, target.open('wb') as out:shutil.copyfileobj(src,out)
    return dest

def install(dest, source_only=False, platform_name=None):
    dest=Path(dest).expanduser().resolve()
    dest.mkdir(parents=True,exist_ok=True)
    if source_only:
        path=dest/('blender-source-'+SOURCE_TAG)
        if not (path/'.git').is_dir():
            cmd=['git','clone','--depth','1','--filter=blob:none','--single-branch',
                 '--branch',SOURCE_TAG,SOURCE,str(path)]
            env=dict(os.environ);env['GIT_LFS_SKIP_SMUDGE']='1'
            try:subprocess.run(cmd,check=True,env=env)
            except (OSError,subprocess.CalledProcessError) as exc:
                raise RuntimeError('Official Blender source clone failed (internet/DNS required)') from exc
        head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if head != SOURCE_COMMIT:raise RuntimeError('Blender source commit mismatch: '+head)
        print(path)
        return path
    pf=platform_name or host_platform()
    if pf not in FILES:raise ValueError('Unsupported binary platform: '+str(pf))
    filename = FILES[pf]
    url = RELEASE+filename
    sha_url = RELEASE+f'blender-{VERSION}.sha256'
    path=dest/filename
    sha_file=dest/(filename+'.checksums')
    try:
        # Always download official checksum file before trusting a cached binary.
        with urllib.request.urlopen(sha_url,timeout=35) as res:
            sha_file.write_bytes(res.read(1024*1024))
        checksums=load_checksums(sha_file)
        expected=checksums.get(filename)
        if not expected:raise RuntimeError('Missing '+filename+' in official manifest')
        if not path.exists():get(url,path,1_000_000_000)
        verify(path, expected)
    except (OSError,urllib.error.URLError) as exc:
        raise RuntimeError('Blender binary could not be downloaded: check internet/DNS; install Blender 4.5 LTS manually') from exc
    extracted=dest/('blender-'+VERSION+'-'+pf)
    binary=extracted/('blender.exe' if pf.startswith('windows') else 'blender')
    if not binary.is_file(): safe_extract(path,dest,'zip' if pf.startswith('windows') else 'tar')
    if not binary.is_file():raise RuntimeError('Blender executable missing after extraction: '+str(binary))
    if pf.startswith('linux'):binary.chmod(binary.stat().st_mode|0o111)
    print(binary)
    return binary

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dest',default=str(Path(__file__).resolve().parent.parent/'vendor'/'Blender'))
    parser.add_argument('--platform',choices=list(FILES),default=None)
    parser.add_argument('--source-only',action='store_true')
    p=parser.parse_args()
    try:install(p.dest,p.source_only,p.platform)
    except Exception as error: parser.exit(1,str(error)+'\n')
