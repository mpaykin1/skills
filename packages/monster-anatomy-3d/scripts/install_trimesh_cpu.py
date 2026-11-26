#!/usr/bin/env python3
"""Install pinned MIT Trimesh into an isolated CPU Python environment."""
import argparse
import subprocess
import sys

VERSION='4.11.1'  # installed and executed in skill authoring environment

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python',default=sys.executable)
    p.add_argument('--install',action='store_true',help='Explicitly install from PyPI (network needed)')
    a=p.parse_args()
    if a.install:
        subprocess.run([a.python,'-m','pip','install',f'trimesh=={VERSION}','numpy>=1.20'],check=True)
    subprocess.run([a.python,'-c',f'import trimesh,numpy; assert trimesh.__version__ == "{VERSION}", trimesh.__version__; print("Trimesh CPU ready:",trimesh.__version__)'],check=True)
if __name__=='__main__':main()
