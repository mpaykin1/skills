#!/usr/bin/env python3
"""Install original MIT howler.js 2.2.4 full distribution (includes spatial plugin).

No CDN or browser-time network request. Uses pinned npm package and preserves license.
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

NAME='howler'
VERSION='2.2.4'
SPEC=f'{NAME}@{VERSION}'

class HowlerVendorError(RuntimeError): pass

def vendor(destination: Path, npm='npm') -> Path:
    exe=shutil.which(npm)
    if not exe: raise HowlerVendorError('npm unavailable: provide actual howler.min.js with --howler-js')
    destination=Path(destination).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix='lia_howler_') as tmp:
        run=subprocess.run([exe,'pack',SPEC,'--json','--ignore-scripts','--pack-destination',tmp],
            cwd=tmp,text=True,capture_output=True,timeout=180,check=False)
        if run.returncode: raise HowlerVendorError('howler download unavailable: '+(run.stderr or run.stdout)[-700:])
        try:
            found=json.loads(run.stdout)
            if len(found)!=1 or (found[0].get('name'),found[0].get('version'))!=(NAME,VERSION):
                raise HowlerVendorError('npm package identity/version mismatch')
            tgz=Path(tmp)/Path(found[0]['filename']).name
            if not tgz.is_file(): raise HowlerVendorError('npm archive missing')
            with tarfile.open(tgz,'r:gz') as tar:
                manifest=json.loads(tar.extractfile('package/package.json').read())
                if (manifest.get('name'),manifest.get('version'),manifest.get('license'))!=(NAME,VERSION,'MIT'):
                    raise HowlerVendorError('Unsigned or incompatible howler manifest')
                js=tar.extractfile('package/dist/howler.min.js').read()
                license_text=tar.extractfile('package/LICENSE.md').read()
            if not 10000<len(js)<250000 or b'howler.js v2.2.4' not in js[:250] or b'Howler' not in js:
                raise HowlerVendorError('Expected complete howler+spatial source distribution')
            if b'Permission is hereby granted' not in license_text:
                raise HowlerVendorError('Official MIT license missing')
            js.decode('utf8')
        except (OSError,KeyError,TypeError,ValueError,UnicodeError,tarfile.TarError) as err:
            if isinstance(err,HowlerVendorError): raise
            raise HowlerVendorError('Invalid howler archive: '+str(err)) from err
        destination.parent.mkdir(parents=True,exist_ok=True)
        tmpfile=destination.with_name(destination.name+'.tmp')
        tmpfile.write_bytes(js);os.replace(tmpfile,destination)
        destination.parent.joinpath('LICENSE.howler.md').write_bytes(license_text)
        destination.parent.joinpath('howler.vendor.json').write_text(json.dumps({
            'package':SPEC,'license':'MIT','sha256':hashlib.sha256(js).hexdigest()},indent=2),'utf8')
        return destination

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--npm',default='npm');a=p.parse_args()
    print(vendor(a.out,a.npm))
