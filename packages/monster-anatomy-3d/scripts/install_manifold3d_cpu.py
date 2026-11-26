#!/usr/bin/env python3
"""Verify or install official MIT/Apache-2.0 Manifold3D CPU Python wheels."""
from __future__ import annotations
import argparse
import importlib.metadata
import subprocess
import sys

PIN='3.5.5'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--install',action='store_true',help='Use pip network install; CPU only')
    args=parser.parse_args()
    if args.install:
        subprocess.run([sys.executable,'-m','pip','install',f'manifold3d=={PIN}','numpy','trimesh'],check=True)
    try:
        v=importlib.metadata.version('manifold3d')
        import manifold3d
        from manifold3d import Manifold, Mesh, OpType, Error
        if v != PIN:raise RuntimeError(f'Expected manifold3d {PIN}; installed {v}')
    except (ImportError,importlib.metadata.PackageNotFoundError) as e:
        raise SystemExit(f'Manifold3D CPU not installed. Run: python -m pip install manifold3d=={PIN} numpy trimesh. {e}')
    print('Real official Manifold3D',v,'CPU available')

if __name__=='__main__':main()
