#!/usr/bin/env python3
"""Install the official Khronos gltf-validator npm module, locally and CPU-only.
Does not touch global npm, perform inference, or silently install at runtime.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

VERSION='2.0.0-dev.3.10'
DEFAULT=Path(__file__).resolve().parent.parent/'vendor'/'gltf-validator-node'

def main():
    p=argparse.ArgumentParser(description='Pin gltf-validator npm for Monster Anatomy 3D')
    p.add_argument('--dest',type=Path,default=DEFAULT)
    p.add_argument('--install',action='store_true',help='Install official npm package (network required)')
    p.add_argument('--verify',action='store_true',help='Verify a previously installed package')
    a=p.parse_args()
    node=shutil.which('node')
    if not node:p.error('Node.js is required (CPU only)')
    ver=subprocess.run([node,'-p','process.versions.node.split(".")[0]'],text=True,capture_output=True,check=True)
    if int(ver.stdout.strip())<18:p.error('Node.js >=18 is required')
    dest=a.dest.expanduser().resolve()
    pkg=dest/'node_modules'/'gltf-validator'/'package.json'
    if a.install:
        npm=shutil.which('npm')
        if not npm:p.error('npm is required')
        dest.mkdir(parents=True,exist_ok=True)
        subprocess.run([npm,'install','--ignore-scripts','--no-audit','--no-fund',
                        '--prefix',str(dest),f'gltf-validator@{VERSION}'],check=True)
    if not pkg.is_file():p.error('Official package missing. Run: python scripts/install_gltf_validator.py --install (requires network).')
    data=json.loads(pkg.read_text(encoding='utf8'))
    if (data.get('name'),data.get('version'))!=('gltf-validator',VERSION):
        p.error('Expected exact Khronos gltf-validator version '+VERSION)
    if not (pkg.parent/'gltf_validator.dart.js').is_file():
        p.error('Compiled official validator runtime missing')
    print('Khronos gltf-validator',VERSION,'available:',pkg.parent)

if __name__=='__main__':main()
