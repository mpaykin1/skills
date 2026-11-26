#!/usr/bin/env python3
"""Fetch the REAL pinned Matter.js 0.20.0 MIT browser UMD; no placeholder engine.

npm is only required at BUILD time; resulting HTML is network independent.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import hashlib

VERSION='0.20.0'
class MatterVendorError(ValueError):pass


def locate(explicit=None):
    raw=explicit or os.environ.get('MATTER_JS_BUNDLE')
    p=Path(raw).expanduser().resolve() if raw else Path(__file__).resolve().parent.parent/'vendor'/'matter.min.js'
    if not p.is_file():
        raise MatterVendorError('Matter.js UMD bundle missing; run matter_vendor.py (requires npm and internet) or pass --matter-js /path/to/matter.min.js')
    code=p.read_bytes()
    if not 30_000<=len(code)<=1_500_000 or b'Matter' not in code[:25000]:
        raise MatterVendorError('Matter.js 0.20.0 browser distribution not recognised')
    try:txt=code.decode('utf-8')
    except UnicodeError as e:raise MatterVendorError('Matter.js browser script is not UTF-8') from e
    return p,txt


def vendor(destination,npm='npm'):
    executable=shutil.which(npm)
    if not executable:
        raise MatterVendorError('Node/npm missing; provide an existing actual matter-js@0.20.0 browser bundle')
    with tempfile.TemporaryDirectory(prefix='lia_matter_') as td:
        proc=subprocess.run([executable,'pack',f'matter-js@{VERSION}','--json','--ignore-scripts','--pack-destination',td],
                            cwd=td,capture_output=True,text=True,timeout=180,check=False)
        if proc.returncode:
            raise MatterVendorError('Cannot download original Matter.js: '+(proc.stderr or proc.stdout)[-900:])
        try:
            packages=json.loads(proc.stdout)
            if len(packages)!=1 or packages[0].get('name')!='matter-js' or packages[0].get('version')!=VERSION:
                raise MatterVendorError('Unexpected matter-js npm package or version')
            tgz=Path(td)/Path(packages[0]['filename']).name
            if not tgz.is_file():raise MatterVendorError('No downloaded tarball')
            with tarfile.open(tgz,'r:gz') as z:
                js=z.extractfile('package/build/matter.min.js').read()
                manifest=json.loads(z.extractfile('package/package.json').read())
                license_name=next((m.name for m in z.getmembers() if m.name.lower() in ('package/license','package/license.md','package/license.txt')),None)
                license_data=z.extractfile(license_name).read() if license_name else b''
            if manifest.get('name')!='matter-js' or manifest.get('version')!=VERSION or manifest.get('license')!='MIT':
                raise MatterVendorError('Incorrect npm package manifest')
            if not license_data or b'Permission is hereby granted' not in license_data:
                raise MatterVendorError('Upstream license missing')
            if not 30_000<=len(js)<=1_500_000 or b'Matter' not in js[:25000]:
                raise MatterVendorError('Matter.js UMD script missing or invalid')
        except (OSError,KeyError,ValueError,tarfile.TarError) as exc:
            raise MatterVendorError('Cannot verify original Matter.js npm tarball: '+str(exc)) from exc
        dest=Path(destination).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_suffix('.tmp');tmp.write_bytes(js);os.replace(tmp,dest)
        (dest.parent/'LICENSE.matter.txt').write_bytes(license_data)
        (dest.parent/'matter.sha256').write_text(hashlib.sha256(js).hexdigest()+'  '+dest.name+'\n','utf8')
        locate(dest)
        return dest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--npm',default='npm')
    a=p.parse_args();print(vendor(a.out,a.npm))
