#!/usr/bin/env python3
"""Optional real, CPU-only build of official apngasm 3.x C++ source.

Requires git, CMake, a C++ compiler, libpng/zlib and Boost development libs.
No bundled binaries, paid services, GPU, scripts from unknown mirrors or CDN.
"""
from __future__ import annotations
import argparse, os, shutil, subprocess, tempfile
from pathlib import Path

UPSTREAM='https://github.com/apngasm/apngasm.git'

class APNGAsmInstallError(RuntimeError):pass

def run(cmd, cwd=None, timeout=180):
    try:p=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as ex:raise APNGAsmInstallError(str(ex)) from ex
    if p.returncode:raise APNGAsmInstallError((p.stderr or p.stdout)[-1200:])
    return p.stdout

def install(destination:Path):
    """Build upstream from source; verify original zlib license and CLI version."""
    from apngasm_bridge import tool_path
    git=shutil.which('git');cmake=shutil.which('cmake')
    if not git or not cmake:raise APNGAsmInstallError('git and CMake are needed to build real apngasm 3.x')
    destination=Path(destination).resolve()
    if destination.exists():raise APNGAsmInstallError('Refusing to overwrite existing apngasm binary')
    with tempfile.TemporaryDirectory(prefix='lia_real_apngasm_') as temp:
        src=Path(temp)/'apngasm';build=Path(temp)/'build'
        run([git,'clone','--depth','1',UPSTREAM,str(src)],timeout=180)
        lic=src/'LICENSE.txt'
        if not lic.is_file() or 'zlib license' not in lic.read_text('utf8').lower():
            raise APNGAsmInstallError('Missing original apngasm zlib license')
        revision=run([git,'rev-parse','HEAD'],cwd=src).strip()
        run([cmake,'-S',str(src),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],timeout=180)
        run([cmake,'--build',str(build),'--parallel','2'],timeout=600)
        candidates=[p for p in build.rglob('apngasm') if p.is_file() and os.access(p,os.X_OK)]
        verified=[]
        for p in candidates:
            try:tool_path(p)
            except Exception:continue
            verified.append(p)
        if len(verified)!=1:raise APNGAsmInstallError('Exactly one original apngasm 3.x executable expected in CMake output')
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(verified[0],destination)
        os.chmod(destination,0o755)
        destination.with_name('LICENSE.apngasm.txt').write_bytes(lic.read_bytes())
        destination.with_name('APNGASM_REVISION.txt').write_text(revision+'\n','utf8')
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(install(a.out))
