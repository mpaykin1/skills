#!/usr/bin/env python3
"""Fetch authentic MIT antopilo/SpriteStacker legacy native editor source, Godot 3.x.

Never claim this old native editor is a Godot4 addon. No fake source files.
Optional numeric-sort patch only after verifying unchanged authentic source Git blob.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess

REPO='https://github.com/antopilo/SpriteStacker.git'
PIN='20b8b3ffae50e709292a428347997a89d38379b6'
FILES={'source/Content/Drawingboard.gd':'6551f391a69dcc7552c8fc8da4209b82d55b2bae',
       'source/Content/Export.gd':'93b3daaafe371f505de7a346cf4ea6f1f1f52542',
       'source/project.godot':'dbf2dca5208269706f5a678f4890430bfec0c7bd'}

def run(cmd,cwd=None):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=False)
    if p.returncode:raise RuntimeError('Authentic source checkout failed: '+p.stderr[-1100:])
    return p.stdout.strip()

def get_native_source(out,patch_numeric_order=False):
    if shutil.which('git') is None:raise RuntimeError('Requires a real git executable and network access')
    out=Path(out).resolve()
    if out.exists():raise RuntimeError('Choose a fresh source folder; never overwrite native editor source')
    run(['git','clone','--no-checkout',REPO,str(out)])
    run(['git','checkout','--detach',PIN],cwd=out)
    if run(['git','rev-parse','HEAD'],cwd=out)!=PIN:raise RuntimeError('Unexpected upstream commit')
    for name,expected in FILES.items():
        actual=run(['git','hash-object',name],cwd=out)
        if actual!=expected:raise RuntimeError('Original upstream Git blob mismatch for '+name)
    if patch_numeric_order:
        p=out/'source/Content/Drawingboard.gd';s=p.read_text('utf8')
        original='\tfolder.list_dir_end()\n\n\treturn files'
        modified='\tfolder.list_dir_end()\n\tif not any:\n\t\tfiles.sort_custom(self, "_lia_numeric_png_order")\n\n\treturn files\n\nfunc _lia_numeric_png_order(a, b):\n\treturn int(a.get_basename()) < int(b.get_basename())'
        if s.count(original)!=1:raise RuntimeError('Legacy GetFiles changed: refuse patch')
        p.write_text(s.replace(original,modified,1),'utf8')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    p.add_argument('--patch-numeric-order',action='store_true',help='Fix old Godot 3 editor import order for numbered PNG files')
    a=p.parse_args();print(get_native_source(a.out,patch_numeric_order=a.patch_numeric_order))
