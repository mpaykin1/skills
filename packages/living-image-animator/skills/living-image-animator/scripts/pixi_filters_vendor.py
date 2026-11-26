#!/usr/bin/env python3
"""Vendor authentic pixi-filters@6.1.5 browser bundle from verified npm package.

Never fake PixiJS filters. npm/network needed only once at BUILD time.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path

VERSION='6.1.5'
PACKAGE=f'pixi-filters@{VERSION}'
class FiltersVendorError(RuntimeError):pass

def vendor(destination:Path,npm='npm')->Path:
    exe=shutil.which(npm)
    if not exe: raise FiltersVendorError('npm unavailable; provide genuine pixi-filters 6.x UMD bundle using --filters-js')
    destination=Path(destination).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix='pixifilters_') as td:
        p=subprocess.run([exe,'pack',PACKAGE,'--json','--ignore-scripts','--pack-destination',td],cwd=td,
                         capture_output=True,text=True,timeout=180,check=False)
        if p.returncode:raise FiltersVendorError('npm pack failed: '+(p.stderr or p.stdout)[-800:])
        try:
            items=json.loads(p.stdout)
            if len(items)!=1 or items[0].get('name')!='pixi-filters' or items[0].get('version')!=VERSION:
                raise FiltersVendorError('Wrong npm package name/version')
            filename=Path(items[0]['filename']).name
            if filename!=f'pixi-filters-{VERSION}.tgz':raise FiltersVendorError('Unexpected npm archive name')
            with tarfile.open(Path(td)/filename,'r:gz') as tar:
                package=json.load(tar.extractfile('package/package.json'))
                if package.get('name')!='pixi-filters' or package.get('version')!=VERSION:
                    raise FiltersVendorError('Unrecognized pixi-filters archive manifest')
                peer=package.get('peerDependencies',{}).get('pixi.js','')
                if '8' not in peer:raise FiltersVendorError('Unsupported PixiJS peer dependency')
                member='package/dist/browser/pixi-filters.min.js'
                js=tar.extractfile(member).read()
                lic=next((s for s in tar.getnames() if s.lower() in ('package/license','package/license.txt','package/license.md')),None)
                notice=tar.extractfile(lic).read() if lic else b''
                if not notice or b'Permission is hereby granted' not in notice:
                    raise FiltersVendorError('Missing authentic MIT license file')
            if not 50_000<=len(js)<=5_000_000 or b'Filter' not in js:
                raise FiltersVendorError('Not a supported official pixi-filters browser distribution')
            js.decode('utf-8')
        except (KeyError,ValueError,TypeError,UnicodeError,OSError,tarfile.TarError) as exc:
            if isinstance(exc,FiltersVendorError):raise
            raise FiltersVendorError('Cannot validate upstream package: '+str(exc)) from exc
        destination.parent.mkdir(parents=True,exist_ok=True)
        temp=destination.with_name(destination.name+'.tmp');temp.write_bytes(js);os.replace(temp,destination)
        destination.parent.joinpath('LICENSE.pixi-filters.txt').write_bytes(notice)
        destination.parent.joinpath('pixi-filters.vendor.json').write_text(json.dumps({
            'package':PACKAGE,'sha256':hashlib.sha256(js).hexdigest(),'license':'MIT'},indent=2),'utf8')
        return destination

if __name__=='__main__':
    pa=argparse.ArgumentParser();pa.add_argument('--out',type=Path,required=True);pa.add_argument('--npm',default='npm')
    a=pa.parse_args();print(vendor(a.out,a.npm))
