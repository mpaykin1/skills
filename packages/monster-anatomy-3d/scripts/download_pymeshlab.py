#!/usr/bin/env python3
"""Pinned external CPU PyMeshLab installer and upstream source checkout.

Does not bundle its GPL source or compiled wheel; on network machine, use
--install (wheel) and optionally --clone-source (full audited repo checkout).
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

SOURCE='https://github.com/cnr-isti-vclab/PyMeshLab.git'
COMMIT='9c30334547750bcbe7126278b16739349643d04b'
VERSION='2025.7.post1'


def run(args):
    subprocess.run([str(x) for x in args],check=True)


def main():
    p=argparse.ArgumentParser(description='PyMeshLab MIT-independent GPL dependency fetch')
    p.add_argument('--install',action='store_true',help='Install official CPU wheels into active Python')
    p.add_argument('--clone-source',type=Path,help='Get upstream Git source at verified commit')
    p.add_argument('--verify',action='store_true',help='Only inspect currently installed dependency')
    a=p.parse_args()
    if a.verify or (not a.install and a.clone_source is None):
        import pymeshlab
        print('Imported real PyMeshLab from',Path(pymeshlab.__file__).resolve())
        return
    if a.install:
        run([sys.executable,'-m','pip','install','pymeshlab=='+VERSION,'numpy'])
    if a.clone_source is not None:
        target=a.clone_source.resolve()
        if target.exists():raise FileExistsError('Source checkout destination exists: '+str(target))
        run(['git','clone','--filter=blob:none','--no-checkout',SOURCE,target])
        run(['git','-C',target,'checkout','--detach',COMMIT])
        rev=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
        if rev!=COMMIT:raise RuntimeError('Upstream commit mismatch: '+rev)
        if not (target/'LICENSE').is_file() or not (target/'README.md').is_file():
            raise RuntimeError('Invalid source checkout')
        print('Verified official PyMeshLab source at',rev)

if __name__=='__main__':main()
