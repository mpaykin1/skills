#!/usr/bin/env python3
"""Vendor authentic MIT YUKA 0.7.8 UMD from an exact, verified npm package.

This standalone AI library complements, but does not replace, real A* routing
and Matter.js collision. No mock AI engine or CDN is allowed in offline HTML.
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

VERSION = '0.7.8'
PACKAGE = f'yuka@{VERSION}'

class YukaVendorError(RuntimeError):
    pass


def locate(provided=None):
    raw = provided or os.environ.get('LIA_YUKA_BUNDLE')
    file = Path(raw).expanduser().resolve() if raw else Path(__file__).resolve().parent.parent/'vendor'/'yuka.js'
    if not file.is_file():
        raise YukaVendorError('Genuine YUKA 0.7.8 UMD missing: --fetch-yuka or --yuka-js /path/to/yuka.js')
    data = file.read_bytes()
    if not 35_000 <= len(data) <= 3_000_000 or not all(symbol in data for symbol in (b'YUKA', b'Vehicle', b'SeekBehavior')):
        raise YukaVendorError('Unrecognized YUKA 0.7.8 browser runtime')
    try:
        decoded = data.decode('utf8')
    except UnicodeDecodeError as e:
        raise YukaVendorError('YUKA UMD must be UTF-8') from e
    return file, decoded


def vendor(out: Path, npm='npm'):
    exe=shutil.which(npm)
    if not exe:
        raise YukaVendorError('npm unavailable; supply authentic pinned YUKA UMD locally')
    with tempfile.TemporaryDirectory(prefix='lia_yuka_') as td:
        proc=subprocess.run([exe,'pack',PACKAGE,'--json','--ignore-scripts','--pack-destination',td],
                            cwd=td,capture_output=True,text=True,timeout=180,check=False)
        if proc.returncode:
            raise YukaVendorError('Cannot download genuine YUKA: '+(proc.stderr or proc.stdout)[-700:])
        try:
            entries=json.loads(proc.stdout)
            if len(entries)!=1 or entries[0].get('name')!='yuka' or entries[0].get('version')!=VERSION:
                raise YukaVendorError('Unexpected npm package identity/version')
            fname=Path(entries[0]['filename']).name
            if fname!=f'yuka-{VERSION}.tgz':
                raise YukaVendorError('Unexpected YUKA npm archive name')
            with tarfile.open(Path(td)/fname,'r:gz') as tar:
                meta=json.loads(tar.extractfile('package/package.json').read())
                if (meta.get('name'),meta.get('version'),meta.get('license'))!=('yuka',VERSION,'MIT'):
                    raise YukaVendorError('Incorrect source metadata/license')
                js=tar.extractfile('package/build/yuka.js').read()
                lic=next((x for x in tar.getnames() if x.lower() in ('package/license','package/license.md','package/license.txt')),None)
                license_bytes=tar.extractfile(lic).read() if lic else b''
                if b'Permission is hereby granted' not in license_bytes:
                    raise YukaVendorError('Official MIT license not supplied with npm package')
            if not 35_000<=len(js)<=3_000_000 or not all(s in js for s in (b'YUKA',b'Vehicle',b'SeekBehavior')):
                raise YukaVendorError('Invalid original UMD distribution')
            js.decode('utf8')
        except (KeyError,ValueError,TypeError,OSError,UnicodeError,tarfile.TarError) as exc:
            raise YukaVendorError('Original YUKA package verification failed: '+str(exc)) from exc
        dest=Path(out).expanduser().resolve()
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_suffix('.tmp');tmp.write_bytes(js);os.replace(tmp,dest)
        (dest.parent/'LICENSE.yuka.txt').write_bytes(license_bytes)
        (dest.parent/'yuka.sha256').write_text(hashlib.sha256(js).hexdigest()+'  '+dest.name+'\n','utf8')
        locate(dest)
        return dest

if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--out',type=Path,required=True)
    cli.add_argument('--npm',default='npm')
    args=cli.parse_args()
    print(vendor(args.out,args.npm))
