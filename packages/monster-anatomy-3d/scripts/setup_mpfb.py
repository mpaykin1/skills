#!/usr/bin/env python3
"""Fetch, build and optionally install the pinned MPFB Blender extension."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

def run(args):
    print('+', ' '.join(str(x) for x in args), flush=True)
    subprocess.run([str(x) for x in args], check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender', default='blender')
    parser.add_argument('--source', default=str(ROOT / 'vendor/MPFB2'))
    parser.add_argument('--offline', action='store_true', help='Do not download; require previously pinned MPFB source')
    parser.add_argument('--install', action='store_true', help='Install extension into local Blender profile')
    args = parser.parse_args()
    src = Path(args.source).resolve()
    run([sys.executable, ROOT/'scripts/download_mpfb.py', '--dest', src] + (['--verify'] if args.offline else []))
    # Blender extension builder may require a license file in its source root.
    license_file = src/'src/mpfb/LICENSE'
    if not license_file.exists():
        shutil.copy2(src/'LICENSE.CODE.md',license_file)
    dist = src/'dist';dist.mkdir(exist_ok=True)
    run([args.blender, '--command', 'extension', 'build', '--source-dir', src/'src/mpfb', '--output-dir', dist])
    packages = sorted(dist.glob('mpfb-*.zip'), key=lambda p:p.stat().st_mtime, reverse=True)
    if not packages:
        packages = sorted(dist.glob('*.zip'), key=lambda p:p.stat().st_mtime, reverse=True)
    if not packages: raise FileNotFoundError('Blender extension build yielded no ZIP')
    print('Built official MPFB2 extension:', packages[0],flush=True)
    if args.install:
        run([args.blender,'--background','--python',ROOT/'scripts/enable_mpfb_blender.py', '--', '--package',packages[0]])

if __name__ == '__main__':main()
