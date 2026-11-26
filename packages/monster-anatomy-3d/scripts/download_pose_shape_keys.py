#!/usr/bin/env python3
"""Fetch and validate official Blender Studio Pose Shape Keys 1.0.0 for Blender 4.5.

No third-party code is bundled in the plugin ZIP. Downloads the official
Blender Extensions dynamic repository package compatible with Blender 4.5.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import tomllib
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

VERSION = '1.0.0'
BLENDER = '4.5.0'
INDEX = 'https://extensions.blender.org/api/v1/extensions/?blender_version=4.5.0&platform=linux-x64'
PKG = 'pose_shape_keys'


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Monster-Anatomy-3D/0.8.0'}),timeout=45) as response:
        return response.read(15_000_000)


def official_package():
    index=json.loads(fetch(INDEX).decode('utf-8'))
    entries=index.get('data',index.get('extensions',[])) if isinstance(index,dict) else index
    valid=[e for e in entries if isinstance(e,dict) and e.get('id')==PKG and e.get('version')==VERSION]
    if len(valid)!=1:
        raise RuntimeError('Official 4.5 package index does not expose Pose Shape Keys 1.0.0; install via official version-history page, then use --zip')
    item=valid[0]
    url=urllib.parse.urljoin('https://extensions.blender.org/api/v1/extensions/',item['archive_url'])
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='extensions.blender.org':
        raise RuntimeError('Refusing non-official package URL: '+url)
    data=fetch(url)
    digest=item.get('archive_hash','')
    if not digest.startswith('sha256:'):
        raise RuntimeError('Official repo entry has no sha256 archive_hash')
    actual=hashlib.sha256(data).hexdigest()
    if digest.split(':',1)[1].lower()!=actual:
        raise RuntimeError('Pose Shape Keys SHA-256 mismatch')
    return data,url,actual


def validate_and_extract(data,dest):
    if len(data)>12_000_000:raise RuntimeError('Unexpectedly large extension archive')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names=z.namelist()
        manifests=[n for n in names if n.endswith('blender_manifest.toml')]
        # Reject archives with multiple plugin roots.
        if len(manifests)!=1:raise RuntimeError('Pose Shape Keys archive missing unique manifest')
        prefix=manifests[0][:-len('blender_manifest.toml')]
        manifest=tomllib.loads(z.read(manifests[0]).decode('utf8'))
        if manifest.get('id')!=PKG or manifest.get('version')!=VERSION or manifest.get('type')!='add-on':
            raise RuntimeError('Unexpected addon identity/version')
        minver=tuple(int(n) for n in manifest.get('blender_version_min','0.0.0').split('.')[:3])
        maxver=tuple(int(n) for n in manifest.get('blender_version_max','99.0.0').split('.')[:3])
        if not (minver<=(4,5,0)<maxver):raise RuntimeError('Official addon not compatible with Blender 4.5')
        if not any('GPL-3.0' in s for s in manifest.get('license',[])):
            raise RuntimeError('Unexpected addon license')
        if not (prefix+'__init__.py') in names:raise RuntimeError('Missing addon entry point')
        dest=Path(dest).expanduser().resolve()
        target=dest/PKG
        if target.exists():
            if not (target/'blender_manifest.toml').is_file():raise RuntimeError('Refusing to overwrite foreign package')
            old=tomllib.loads((target/'blender_manifest.toml').read_text(encoding='utf8'))
            if old.get('id')!=PKG:raise RuntimeError('Existing addon identity mismatch')
        dest.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest) as tmp:
            staging=Path(tmp)/PKG; staging.mkdir()
            for info in z.infolist():
                if info.is_dir() or not info.filename.startswith(prefix):continue
                if ((info.external_attr >> 16) & 0o170000)==0o120000:raise RuntimeError('Symlink not allowed in addon ZIP')
                relative=info.filename[len(prefix):]
                if not relative:continue
                rel=Path(relative)
                if rel.is_absolute() or '..' in rel.parts or len(rel.parts)>9:raise RuntimeError('Unsafe ZIP path')
                if info.file_size>5_000_000:raise RuntimeError('Unexpected large source file')
                out=staging/rel
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(z.read(info))
            if target.exists():shutil.rmtree(target)
            shutil.move(str(staging),str(target))
        return target


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dest',default=str(Path(__file__).resolve().parent.parent/'vendor'/'pose-shape-keys'))
    p.add_argument('--zip',default='',help='Previously downloaded official 1.0.0 ZIP for offline use')
    p.add_argument('--verify',action='store_true',help='Do not access network; validate already extracted addon')
    a=p.parse_args()
    out=Path(a.dest).expanduser().resolve()
    if a.verify:
        pth=out/PKG/'blender_manifest.toml'
        if not pth.is_file():p.error('Pose Shape Keys is not installed: '+str(pth))
        m=tomllib.loads(pth.read_text(encoding='utf8'))
        if m.get('id')!=PKG or m.get('version')!=VERSION:p.error('Expected 1.0.0 only')
        print('Verified',pth.parent)
        return
    try:
        if a.zip:
            data=Path(a.zip).read_bytes(); source='local official extension ZIP'
        else:
            data,source,digest=official_package()
        directory=validate_and_extract(data,out)
        print('Installed compatible official add-on:',directory)
        print('Source:',source)
        print('SHA-256:',hashlib.sha256(data).hexdigest())
    except Exception as exc:
        p.exit(2,'Pose Shape Keys not installed: '+str(exc)+'\n')

if __name__=='__main__':main()
