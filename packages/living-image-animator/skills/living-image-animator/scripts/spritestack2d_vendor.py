#!/usr/bin/env python3
"""Install the ORIGINAL SpriteStack2D MIT Godot addon from its pinned GitHub commit.

No fake stand-in node, no scraping generated examples, no hidden network at runtime.
Only the published original GDScript addon and its MIT license are accepted.
"""
from __future__ import annotations
import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

UPSTREAM='https://github.com/VitSoonYoung/SpriteStack2D.git'
REV='65f6d8dee65575ef3ee0f164698a2a1ecf93872b'
BLOBS={
 'sprite_stack_2d.gd':'c466b11ff0e51562c34cfc54ce0b16c7b2d719c7',
 'plugin.gd':'8aea5c837e55cb792ad89720e137f6e7459cc465',
 'plugin.cfg':'f2bb9aeff1d76486f31ea96beda327ac3606b8fd',
}
LICENSE_BLOB='8f0f9fb2eb59dfd0ec85ac47da6e50ff98785971'

class SpriteStack2DVendorError(RuntimeError):pass

def blob_sha(data:bytes)->str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def validate(source:Path)->tuple[Path,Path]:
    """Accept official checkout root, or an addon folder with official LICENSE nearby."""
    source=Path(source).expanduser().resolve()
    if (source/'addons/sprite_stack_2d').is_dir():
        addon=source/'addons/sprite_stack_2d';license_path=source/'LICENSE'
    elif (source/'sprite_stack_2d.gd').is_file():
        addon=source
        license_path=next((p for p in (source/'LICENSE',source.parent/'LICENSE',source.parent.parent/'LICENSE',source.parent/'LICENSE.SpriteStack2D.txt') if p.is_file()),source/'LICENSE')
    else:raise SpriteStack2DVendorError('Supply the genuine upstream checkout or addons/sprite_stack_2d directory')
    for name,expected in BLOBS.items():
        path=addon/name
        if not path.is_file() or blob_sha(path.read_bytes())!=expected:
            raise SpriteStack2DVendorError('Original upstream SpriteStack2D source mismatch: '+name)
    if not (addon/'icon_sprite_stack_2d.svg').is_file():
        raise SpriteStack2DVendorError('Official SpriteStack2D editor icon missing')
    if not license_path.is_file() or blob_sha(license_path.read_bytes())!=LICENSE_BLOB:
        raise SpriteStack2DVendorError('Original upstream MIT license missing/modified')
    return addon,license_path

def install(target:Path,git='git')->Path:
    target=Path(target).resolve()
    if target.exists():raise SpriteStack2DVendorError('Addon destination exists; refusing replacement')
    exe=shutil.which(git)
    if not exe:raise SpriteStack2DVendorError('git is required for authentic SpriteStack2D source installation')
    with tempfile.TemporaryDirectory(prefix='lia_godot_stack2d_') as td:
        src=Path(td)/'source'
        def run(args,seconds=150):
            try:p=subprocess.run([exe,*args],capture_output=True,text=True,timeout=seconds,check=False)
            except (OSError,subprocess.TimeoutExpired) as e:raise SpriteStack2DVendorError(str(e)) from e
            if p.returncode:raise SpriteStack2DVendorError('Official SpriteStack2D checkout failed: '+(p.stderr or p.stdout)[-900:])
            return p.stdout
        run(['clone','--depth','1','--filter=blob:none',UPSTREAM,str(src)])
        head=run(['-C',str(src),'rev-parse','HEAD']).strip()
        if head!=REV:
            run(['-C',str(src),'fetch','--depth','1','origin',REV])
            run(['-C',str(src),'checkout','--detach',REV])
        if run(['-C',str(src),'rev-parse','HEAD']).strip()!=REV:
            raise SpriteStack2DVendorError('Upstream commit does not match pinned approved source')
        addon,lic=validate(src)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(addon,target,ignore=shutil.ignore_patterns('*.import','*.uid'))
        target.parent.parent.joinpath('LICENSE').write_bytes(lic.read_bytes())
        validate(target.parent.parent)
    return target

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--git',default='git')
    a=p.parse_args();print(install(a.out,a.git))
