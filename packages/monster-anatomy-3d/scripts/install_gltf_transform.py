#!/usr/bin/env python3
"""Install official CPU-only glTF-Transform v4.5.1 locally, no global npm changes.
Run once on a machine with network. Never modifies the user's system-wide npm.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

VERSION='4.5.1'
ROOT=Path(__file__).resolve().parent.parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dest',type=Path,default=ROOT/'vendor'/'gltf-transform-node')
    p.add_argument('--install',action='store_true',help='Fetch official pinned NPM CLI; requires internet')
    p.add_argument('--verify',action='store_true',help='Only inspect local installation')
    a=p.parse_args()
    node=shutil.which('node');npm=shutil.which('npm')
    if not node or not npm:p.error('Node.js >=20 and npm required (CPU only)')
    node_version=subprocess.run([node,'-p','process.versions.node.split(".")[0]'],capture_output=True,text=True,check=True)
    if int(node_version.stdout.strip())<20:p.error('Node.js >=20 required')
    dest=a.dest.expanduser().resolve()
    package=dest/'node_modules'/'@gltf-transform'/'cli'/'package.json'
    if a.install:
        dest.mkdir(parents=True,exist_ok=True)
        subprocess.run([npm,'install','--no-audit','--no-fund','--prefix',str(dest),
                        f'@gltf-transform/cli@{VERSION}'],check=True)
    if not package.is_file():p.error('Official CLI not installed. Run --install with internet access.')
    import json
    manifest=json.loads(package.read_text(encoding='utf-8'))
    if manifest.get('name')!='@gltf-transform/cli' or manifest.get('version')!=VERSION:
        p.error('Installed CLI version differs from pinned version')
    cli=dest/'node_modules'/'.bin'/('gltf-transform.cmd' if sys.platform.startswith('win') else 'gltf-transform')
    if not cli.is_file():p.error('Package is present but executable missing')
    print(cli)

if __name__=='__main__':main()
