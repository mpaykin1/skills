"""Stage the unmodified pinned official source as a local add-on archive.
Runs git only on an explicitly supplied, reviewed local clone. No network or enable.
"""
import argparse, hashlib, subprocess, zipfile
from pathlib import Path
REV='a0741767d1be631dec889c7bf4e164e64b3cd9b6'
LICENSE_BLOB='153d416dc8d2d60076698ec3cbfce34d91436a03'
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],timeout=30)
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();root=a.source.resolve();out=a.out.resolve()
    if out.exists() or out.suffix!='.zip':raise ValueError('new zip required')
    if git(root,'rev-parse','HEAD').decode().strip()!=REV:raise ValueError('wrong revision')
    if git(root,'rev-parse',REV+':LICENSE.md').decode().strip()!=LICENSE_BLOB:raise ValueError('wrong license blob')
    if git(root,'status','--porcelain').strip():raise ValueError('dirty source')
    out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','-C',str(root),'archive','--format=zip','--prefix=rokoko_studio_live/','-o',str(out),REV],check=True,timeout=120)
    with zipfile.ZipFile(out) as z:
        names=z.namelist()
        if 'rokoko_studio_live/__init__.py' not in names or 'rokoko_studio_live/LICENSE.md' not in names:raise ValueError('invalid add-on archive')
    print('Staged only, not installed:',out,hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
