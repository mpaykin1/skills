#!/usr/bin/env python3
"""Obtain genuine open-source PathFinding.js 0.4.18 and browserify it locally.

Requires Node/npm plus network when dependencies are not cached. No fake
PathFinding.js substitute is supplied; generated HTML remains genuinely offline.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

VERSION='0.4.18'
BROWSERIFY_VERSION='17.0.1'

class PathFindingVendorError(ValueError):pass

def locate(path=None):
    if path is not None:
        p=Path(path).expanduser().resolve()
    else:
        raw=os.environ.get('PATHFINDING_JS_BUNDLE')
        p=Path(raw).expanduser().resolve() if raw else Path(__file__).resolve().parent.parent/'vendor'/'pathfinding-browser.js'
    if not p.is_file():raise PathFindingVendorError('Real PathFinding.js bundle missing; install via pathfinding_vendor.py or supply --pathfinding-js')
    code=p.read_bytes()
    if not 3000<=len(code)<=2_000_000 or not any(w in code for w in (b'PathFinding',b'PathFinding.js',b'AStarFinder')):
        raise PathFindingVendorError('Cannot identify genuine PathFinding.js browser runtime')
    if b'PF=' not in code and b'PF ' not in code and b'PF;' not in code and b'PF)' not in code:
        raise PathFindingVendorError('Browser distribution lacks expected PF global')
    return p,code.decode('utf8')

def vendor(destination,npm='npm'):
    exe=shutil.which(npm)
    if not exe:raise PathFindingVendorError('npm missing; supply --pathfinding-js existing genuine browser bundle')
    with tempfile.TemporaryDirectory(prefix='lia_pf_') as tmp:
        cmd=[exe,'install','--prefix',tmp,'--ignore-scripts','--no-audit','--no-fund',
             f'pathfinding@{VERSION}',f'browserify@{BROWSERIFY_VERSION}']
        proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=240,check=False)
        if proc.returncode:raise PathFindingVendorError('Unable to download PathFinding.js: '+(proc.stderr or proc.stdout)[-800:])
        root=Path(tmp);pkg=root/'node_modules'/'pathfinding'
        meta=json.loads((pkg/'package.json').read_text('utf8'))
        if meta.get('name')!='pathfinding' or meta.get('version')!=VERSION:
            raise PathFindingVendorError('Downloaded incorrect PathFinding.js release')
        licensefile=next((v for v in pkg.iterdir() if v.name.lower() in ('license','license.txt','license.md')),None)
        if licensefile is None:
            # Source docs may carry MIT license if release omits LICENSE file.
            readme=pkg/'README.md'
            if not readme.is_file() or 'MIT' not in readme.read_text('utf8'):
                raise PathFindingVendorError('No upstream license evidence')
            license_text=readme.read_text('utf8')
        else:license_text=licensefile.read_text('utf8')
        browserify=root/'node_modules'/'.bin'/'browserify'
        if not browserify.exists():raise PathFindingVendorError('Pinned browserify not installed')
        output=root/'pathfinding-browser.js'
        cmd=[str(browserify),'-r','pathfinding','-s','PF','-o',str(output)]
        proc=subprocess.run(cmd,cwd=tmp,capture_output=True,text=True,timeout=120,check=False)
        if proc.returncode:raise PathFindingVendorError('Browserify failed: '+(proc.stderr or proc.stdout)[-900:])
        destination=Path(destination).resolve();destination.parent.mkdir(parents=True,exist_ok=True)
        code=output.read_text('utf8');
        if len(code)<3000 or 'AStarFinder' not in code:raise PathFindingVendorError('Bundled PathFinding.js missing A* solver')
        # Dedicated PF window binding, no CDN/no external imports at runtime.
        code += '\n;window.PF=PF;\n'
        destination.write_text('/* PathFinding.js 0.4.18; MIT; original project https://github.com/qiao/PathFinding.js */\n'+code,'utf8')
        (destination.parent/'LICENSE.pathfinding.txt').write_text(license_text,'utf8')
        return locate(destination)[0]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--npm',default='npm');a=p.parse_args();print(vendor(a.out,a.npm))
