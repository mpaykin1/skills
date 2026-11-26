#!/usr/bin/env python3
"""Vendor the official MIT nipplejs@1.0.4 UMD browser distribution.

No CDN is used by the resulting offline HTML. A real npm package is required;
never substitute a hand-drawn joystick for the external source dependency.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

VERSION='1.0.4'
PACKAGE=f'nipplejs@{VERSION}'

class NippleVendorError(RuntimeError):pass

def locate(path=None):
    raw=path or os.environ.get('LIA_NIPPLEJS_BUNDLE')
    p=Path(raw).expanduser().resolve() if raw else Path(__file__).resolve().parent.parent/'vendor'/'nipplejs.min.js'
    if not p.is_file():raise NippleVendorError('Real nipplejs@1.0.4 UMD missing: use --fetch-nipple or --nipple-js /path/to/index.min.js')
    raw=p.read_bytes()
    if not 4000<=len(raw)<=600_000 or b'nipple' not in raw.lower():
        raise NippleVendorError('This does not look like the official nipplejs browser distribution')
    try:txt=raw.decode('utf-8')
    except UnicodeDecodeError as e:raise NippleVendorError('nipplejs script is not UTF-8') from e
    if not any(s in txt for s in ('nipplejs','nippleJS','NippleJS')):
        raise NippleVendorError('nipplejs symbol absent')
    return p,txt

def vendor(destination:Path,npm='npm'):
    exe=shutil.which(npm)
    if not exe:raise NippleVendorError('npm not installed; provide genuine original nipplejs 1.0.4 UMD')
    with tempfile.TemporaryDirectory(prefix='lia_nipple_1_') as tmp:
        args=[exe,'pack',PACKAGE,'--json','--ignore-scripts','--pack-destination',tmp]
        proc=subprocess.run(args,cwd=tmp,capture_output=True,text=True,timeout=120,check=False)
        if proc.returncode:raise NippleVendorError('Cannot fetch original nipplejs: '+(proc.stderr or proc.stdout)[-900:])
        try:
            result=json.loads(proc.stdout)
            if len(result)!=1 or result[0].get('name')!='nipplejs' or result[0].get('version')!=VERSION:
                raise NippleVendorError('Wrong npm package or version')
            fname=Path(result[0]['filename']).name
            if fname!=f'nipplejs-{VERSION}.tgz':raise NippleVendorError('Unexpected npm package filename')
            with tarfile.open(Path(tmp)/fname,'r:gz') as tar:
                data=json.loads(tar.extractfile('package/package.json').read())
                if (data.get('name'),data.get('version'),data.get('license'))!=('nipplejs',VERSION,'MIT'):
                    raise NippleVendorError('Incorrect upstream npm metadata or license')
                # Official Rollup UMD output, built from upstream TS and included in npm dist.
                members=tar.getnames()
                jsname=next((x for x in ('package/dist/index.min.js','package/dist/index.js') if x in members),None)
                if not jsname:raise NippleVendorError('Original UMD browser build not in npm tarball')
                js=tar.extractfile(jsname).read()
            if not 4000<=len(js)<=600000 or b'nipple' not in js.lower():
                raise NippleVendorError('Incorrect UMD distribution')
            js.decode('utf8')
        except (OSError,KeyError,ValueError,TypeError,UnicodeError,tarfile.TarError) as exc:
            raise NippleVendorError('Cannot validate genuine npm nipplejs: '+str(exc)) from exc
        destination=Path(destination).resolve();destination.parent.mkdir(parents=True,exist_ok=True)
        temp=destination.with_suffix('.tmp');temp.write_bytes(js);os.replace(temp,destination)
        notice=Path(__file__).parent.parent/'references'/'LICENSE.nipplejs.txt'
        if not notice.is_file():raise NippleVendorError('Original MIT license notice is missing')
        destination.parent.joinpath('LICENSE.nipplejs.txt').write_bytes(notice.read_bytes())
        destination.parent.joinpath('nipplejs.sha256').write_text(hashlib.sha256(js).hexdigest()+'\n','utf8')
        locate(destination)
        return destination

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--npm',default='npm')
    a=p.parse_args();print(vendor(a.out,a.npm))
