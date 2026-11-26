#!/usr/bin/env python3
"""Fetch the AUTHENTIC official MIT Three.js 0.187.0 standalone ESM through npm.
Does not invent/mimic runtime on missing npm or network. No CDN at runtime.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, tarfile, tempfile
from pathlib import Path

VERSION='0.187.0'

def vendor(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise RuntimeError('Three.js bundle exists; refusing to overwrite it')
    npm=shutil.which('npm')
    if not npm:raise RuntimeError('Official npm is required to download actual Three.js; provide --three-js otherwise')
    with tempfile.TemporaryDirectory(prefix='lia_three_npm_') as d:
        cmd=[npm,'pack','three@'+VERSION,'--ignore-scripts','--silent','--pack-destination',d]
        try:p=subprocess.run(cmd,cwd=d,capture_output=True,text=True,timeout=150,check=False)
        except (OSError,subprocess.TimeoutExpired) as e:raise RuntimeError('Official Three.js npm download failed: '+str(e)) from e
        if p.returncode:raise RuntimeError('Actual npm Three.js download unavailable: '+p.stderr[-600:])
        name=Path(d)/('three-'+VERSION+'.tgz')
        if not name.is_file():raise RuntimeError('Official pinned npm tarball absent')
        with tarfile.open(name,'r:gz') as tar:
            members={e.name:e for e in tar.getmembers() if e.isfile()}
            for wanted in ['package/package.json','package/build/three.module.js','package/LICENSE']:
                if wanted not in members:raise RuntimeError('Genuine Three.js package missing '+wanted)
            pkg=json.loads(tar.extractfile(members['package/package.json']).read())
            if pkg.get('name')!='three' or pkg.get('version')!=VERSION or pkg.get('license')!='MIT':
                raise RuntimeError('Unexpected source/rights for installed Three.js')
            source=tar.extractfile(members['package/build/three.module.js']).read()
            lic=tar.extractfile(members['package/LICENSE']).read()
            if not 200_000<len(source)<5_000_000 or b'Data3DTexture' not in source:
                raise RuntimeError('Incomplete real Three.js 3D textures runtime')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(source)
        destination.with_name('LICENSE.three.txt').write_bytes(lic)
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(vendor(a.out))
