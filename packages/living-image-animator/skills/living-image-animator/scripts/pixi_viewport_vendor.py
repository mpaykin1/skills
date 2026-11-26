#!/usr/bin/env python3
"""Acquire authentic, pinned pixi-viewport v7 UMD for standalone PixiJS v8.

Uses npm tarball metadata + included license. Never substitutes handwritten pan
logic for the actual library and never downloads paid/opaque weights.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import os

VERSION='7.0.3'
PACKAGE='pixi-viewport@'+VERSION

class ViewportVendorError(ValueError): pass

def vendor(destination:Path,npm='npm')->Path:
    npm_bin=shutil.which(npm)
    if not npm_bin:
        raise ViewportVendorError('npm missing; provide --viewport-js to the genuine pixi-viewport v7 UMD bundle')
    destination=Path(destination).resolve()
    with tempfile.TemporaryDirectory(prefix='viewport_npm_') as tmp:
        p=subprocess.run([npm_bin,'pack',PACKAGE,'--json','--ignore-scripts','--pack-destination',tmp],
                         cwd=tmp,text=True,capture_output=True,timeout=180,check=False)
        if p.returncode:
            raise ViewportVendorError('Cannot obtain authentic pixi-viewport '+VERSION+': '+(p.stderr or p.stdout)[-850:])
        try:
            metadata=json.loads(p.stdout)
            if len(metadata)!=1 or metadata[0]['name']!='pixi-viewport' or metadata[0]['version']!=VERSION:
                raise ViewportVendorError('npm returned unexpected package/version')
            name=Path(metadata[0]['filename']).name
            if name!=f'pixi-viewport-{VERSION}.tgz':
                raise ViewportVendorError('Unexpected npm archive name')
            with tarfile.open(Path(tmp)/name,'r:gz') as tar:
                pkg=json.load(tar.extractfile('package/package.json'))
                if pkg.get('name')!='pixi-viewport' or pkg.get('version')!=VERSION or pkg.get('license')!='MIT':
                    raise ViewportVendorError('Unverified upstream manifest')
                member='package/dist/pixi_viewport.umd.cjs'
                payload=tar.extractfile(member).read()
                license_file=next((n for n in tar.getnames() if n.lower() in ('package/license','package/license.txt','package/license.md')),None)
                license_data=tar.extractfile(license_file).read() if license_file else None
                if not license_data or b'MIT' not in license_data:
                    raise ViewportVendorError('MIT LICENSE is not present in npm package')
            if not (15000<=len(payload)<=2_500_000):
                raise ViewportVendorError('Unexpected compiled viewport runtime length')
            decoded=payload.decode('utf-8')
            if 'Viewport' not in decoded or 'pixi_viewport' not in decoded[:1000]:
                raise ViewportVendorError('Not the expected UMD viewport distribution')
        except (KeyError,TypeError,ValueError,UnicodeError,OSError,tarfile.TarError) as err:
            if isinstance(err,ViewportVendorError):raise
            raise ViewportVendorError('pixi-viewport package invalid: '+str(err)) from err
        destination.parent.mkdir(parents=True,exist_ok=True)
        staged=destination.with_suffix('.tmp')
        staged.write_bytes(payload)
        os.replace(staged,destination)
        destination.with_name('LICENSE.pixi-viewport.txt').write_bytes(license_data)
        return destination

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--npm',default='npm')
    args=p.parse_args()
    print(vendor(args.out,args.npm))

if __name__=='__main__':main()
