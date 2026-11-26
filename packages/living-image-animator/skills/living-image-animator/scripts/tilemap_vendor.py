#!/usr/bin/env python3
"""Acquire genuine @pixi/tilemap v5 UMD from the official MIT npm tarball."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tarfile, tempfile, hashlib
from pathlib import Path

PACKAGE='@pixi/tilemap@5.0.2'
class TileVendorError(RuntimeError):pass

def vendor(destination:Path,npm='npm'):
    exe=shutil.which(npm)
    if not exe:raise TileVendorError('npm unavailable; supply authentic --tilemap-js package/dist/pixi-tilemap.js')
    destination=Path(destination).resolve()
    with tempfile.TemporaryDirectory(prefix='lia_tilemap_') as td:
        p=subprocess.run([exe,'pack',PACKAGE,'--json','--ignore-scripts','--pack-destination',td],cwd=td,capture_output=True,text=True,timeout=160,check=False)
        if p.returncode:raise TileVendorError('Cannot download genuine @pixi/tilemap: '+(p.stderr or p.stdout)[-500:])
        try:
            record=json.loads(p.stdout)
            if len(record)!=1 or record[0].get('name')!='@pixi/tilemap' or record[0].get('version')!='5.0.2':raise TileVendorError('Unexpected npm package metadata')
            filename=Path(record[0]['filename']).name
            with tarfile.open(Path(td)/filename,'r:gz') as tar:
                pkg=json.load(tar.extractfile('package/package.json'))
                if pkg.get('name')!='@pixi/tilemap' or pkg.get('version')!='5.0.2' or pkg.get('license')!='MIT':raise TileVendorError('Invalid original manifest/license')
                if '8' not in pkg.get('peerDependencies',{}).get('pixi.js',''):raise TileVendorError('Unsupported PixiJS peer')
                js=tar.extractfile('package/dist/pixi-tilemap.js').read()
            if not 30_000<=len(js)<=5_000_000 or b'CompositeTilemap' not in js:raise TileVendorError('Unsupported compiled browser distribution')
            js.decode('utf8')
        except (KeyError,OSError,ValueError,TypeError,UnicodeDecodeError,tarfile.TarError) as e:
            raise TileVendorError('Unexpected official tilemap archive: '+str(e)) from e
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(js)
    destination.with_name('tilemap-source.json').write_text(json.dumps({'package':PACKAGE,'sha256':hashlib.sha256(js).hexdigest()},indent=2),'utf8')
    return destination

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);p=a.parse_args();print(vendor(p.out))
