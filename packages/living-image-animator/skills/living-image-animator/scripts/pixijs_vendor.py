#!/usr/bin/env python3
"""Install a *real* pinned PixiJS browser distribution via npm's verified tarball.

The engine is an external MIT-licensed dependency; do not generate a fake
replacement when npm or the network is unavailable.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

VERSION='8.23.0'
PACKAGE=f'pixi.js@{VERSION}'

class PixiVendorError(ValueError): pass

def vendor(destination:Path, npm='npm'):
    binary=shutil.which(npm)
    if not binary: raise PixiVendorError('npm executable missing; install Node/npm or provide --pixi-js path to genuine PixiJS v8 browser bundle')
    destination=Path(destination).resolve()
    with tempfile.TemporaryDirectory(prefix='pixi_8_npm_') as td:
        proc=subprocess.run([binary,'pack',PACKAGE,'--json','--ignore-scripts','--pack-destination',td], cwd=td,
                            capture_output=True,text=True,timeout=180,check=False)
        if proc.returncode!=0:raise PixiVendorError('Cannot download exact PixiJS '+VERSION+': '+(proc.stderr or proc.stdout)[-700:])
        try:
            info=json.loads(proc.stdout)
            if len(info)!=1 or info[0]['name']!='pixi.js' or info[0]['version']!=VERSION:
                raise PixiVendorError('npm tarball metadata not for pinned PixiJS '+VERSION)
            filename=Path(info[0]['filename']).name
            if filename!=f'pixi.js-{VERSION}.tgz':raise PixiVendorError('Unexpected npm tarball file name')
            tgz=Path(td)/filename
            if not tgz.is_file():raise PixiVendorError('npm pack did not create tarball')
            with tarfile.open(tgz,'r:gz') as pkg:
                js=pkg.extractfile('package/dist/pixi.min.js').read()
                license_file=next((x for x in pkg.getmembers() if x.name.lower() in ('package/license','package/license.md','package/license.txt')),None)
                license_bytes=pkg.extractfile(license_file).read() if license_file else None
                metadata=json.loads(pkg.extractfile('package/package.json').read())
            if metadata.get('name')!='pixi.js' or metadata.get('version')!=VERSION:raise PixiVendorError('Packed PixiJS metadata mismatch')
            if len(js)<50000 or len(js)>8_000_000 or b'Pixi' not in js[:30000]:raise PixiVendorError('Unrecognized PixiJS distribution')
            if not license_bytes or b'MIT' not in license_bytes:raise PixiVendorError('Missing MIT license in vendor distribution')
        except (KeyError,ValueError,OSError,tarfile.TarError) as exc:
            raise PixiVendorError('Cannot verify exact npm PixiJS distribution: '+str(exc)) from exc
        destination.parent.mkdir(parents=True,exist_ok=True)
        tmp=destination.with_suffix('.tmp')
        tmp.write_bytes(js)
        os.replace(tmp,destination)
        destination.with_name('LICENSE.pixijs.txt').write_bytes(license_bytes)
        return destination

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--npm',default='npm')
    args=p.parse_args()
    print(vendor(args.out,args.npm))
