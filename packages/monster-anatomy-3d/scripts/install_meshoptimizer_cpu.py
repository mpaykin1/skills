#!/usr/bin/env python3
"""Install verified official gltfpack v1.3 release (CPU binary, no CUDA)."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import stat
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

VERSION='v1.3'
RELEASE='https://github.com/zeux/meshoptimizer/releases/download/'+VERSION+'/'
FILES={
 'Linux': ('gltfpack-ubuntu.zip','0666d9dc40d60fe5b9a45f3fc24f8e6ca87112974bd5de9ca57152aa13d06017'),
 'Windows': ('gltfpack-windows.zip','f6e9c09d66af23da3da71b86f0652d2413e81c734e0aecd1cd3d0e6e6e8645c0'),
 'Darwin': ('gltfpack-macos.zip','1002fe6a437aa005eca541502c27b8d2b184f91f4ad0c6d282e3614a1e35e75a'),
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest',default='vendor/gltfpack-v1.3')
    p.add_argument('--archive',type=Path,help='Previously downloaded official gltfpack release ZIP; offline option')
    p.add_argument('--verify',action='store_true',help='Check installed executable exists without downloading')
    args=p.parse_args()
    arch=platform.system()
    if arch not in FILES:p.error('Supported platforms: Linux, Windows, macOS')
    if arch=='Darwin' and platform.machine().lower() not in ('arm64','aarch64'):
        p.error('Official v1.3 macOS binaries are Apple Silicon only; compile from source on Intel')
    if platform.machine().lower() not in ('amd64','x86_64','arm64','aarch64'):
        p.error('Unsupported CPU platform; compile gltfpack from official source')
    dest=Path(args.dest).expanduser().resolve();exe=dest/('gltfpack.exe' if arch=='Windows' else 'gltfpack')
    if args.verify:
        if not exe.is_file():p.error('gltfpack not installed: '+str(exe))
        print(str(exe));return
    if exe.exists():p.error('Destination executable already exists; never overwrite previous install')
    archive_name,expected=FILES[arch]
    with tempfile.TemporaryDirectory(prefix='meshoptimizer-v1.3-') as td:
        zip_path=Path(td)/archive_name
        if args.archive:
            src=args.archive.expanduser().resolve()
            if not src.is_file():p.error('Offline archive not found: '+str(src))
            shutil.copyfile(src,zip_path)
        else:
            # The official release is pinned; requests are explicitly opt-in via this command.
            with urlopen(RELEASE+archive_name,timeout=60) as response, zip_path.open('wb') as outf:
                shutil.copyfileobj(response,outf)
        actual=hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if actual!=expected:
            raise RuntimeError('Official '+VERSION+' SHA-256 mismatch; archive rejected')
        with ZipFile(zip_path) as z:
            files=[i for i in z.infolist() if not i.is_dir() and Path(i.filename).name.lower()==exe.name.lower()]
            if len(files)!=1:raise RuntimeError('Official archive must contain exactly one gltfpack executable')
            info=files[0]
            if info.file_size>200*1024*1024:raise RuntimeError('Unexpectedly oversized gltfpack binary')
            extracted=Path(td)/exe.name
            with z.open(info) as stream,extracted.open('wb') as target:
                shutil.copyfileobj(stream,target)
        dest.mkdir(parents=True,exist_ok=True)
        temp_exe=dest/(exe.name+'.tmp')
        shutil.move(str(extracted),str(temp_exe))
        temp_exe.chmod(temp_exe.stat().st_mode|stat.S_IXUSR)
        os.replace(temp_exe,exe)
    print('[meshoptimizer v1.3 verified]',exe)

if __name__=='__main__':main()
