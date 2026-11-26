#!/usr/bin/env python3
"""Cpp2IL -> ILSpy bridge for authorized Unity IL2CPP native builds.

Recover *approximate* managed DLLs / decompiled C# when possible; never claim
complete C# recovery or playable HTML. No untrusted game executable is launched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from typing import Any
from install_cpp2il import resolve as resolve_cpp2il, COMMIT as CPP2IL_COMMIT

BINARY_NAMES={'gameassembly.dll','gameassembly.so','libil2cpp.so','gameassembly.dylib'}
CONTAINERS={'.apk','.xapk','.apkm','.ipa','.tipa'}


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def normalized_source(source: Path) -> Path:
    p=source.expanduser().resolve(strict=True)
    if p.is_file() and p.suffix.lower() in ('.exe','.x86','.x86_64'):
        return p.parent
    if p.is_file() and p.name.lower() in BINARY_NAMES:
        return p.parent
    if p.is_dir() and p.name.endswith('_Data'):
        return p.parent
    return p


def inspect_il2cpp(src: Path) -> dict[str,Any]:
    """Bounded presence check; never executes original binaries or expands APKs."""
    if src.is_file():
        if src.suffix.lower() not in CONTAINERS:
            raise ValueError('Expected Unity IL2CPP game directory, *_Data folder, executable, or APK/IPA archive')
        if not zipfile.is_zipfile(src):raise ValueError('Not a valid Unity mobile game archive')
        with zipfile.ZipFile(src) as f:
            files=f.namelist()
            metadata=[n for n in files if n.endswith('/global-metadata.dat')]
            native=[n for n in files if n.endswith('/libil2cpp.so') or n.endswith('/GameAssembly.dll')]
        if not metadata or not native:
            raise ValueError('Mobile archive does not contain both global-metadata.dat and an IL2CPP native binary')
        return {'game_root':str(src),'metadata':metadata[:12],'native_binary':native[:12],'archive':True}
    if not src.is_dir():raise ValueError('Missing Unity IL2CPP directory')
    metadata=[];native=[]
    for root,dirs,files in os.walk(src,followlinks=False):
        base=Path(root)
        depth=len(base.relative_to(src).parts)
        dirs[:]=[d for d in dirs if depth<7 and not (base/d).is_symlink() and d not in ('Library','Temp','node_modules','.git')]
        for name in files:
            path=base/name
            if path.is_symlink():continue
            if name.lower()=='global-metadata.dat':metadata.append(str(path.relative_to(src)))
            if name.lower() in BINARY_NAMES:native.append(str(path.relative_to(src)))
        if len(metadata)>50 or len(native)>50:break
    if not metadata or not native:
        raise ValueError('Unity IL2CPP metadata + native binary not found. This is likely a Mono or non-IL2CPP build; use ILSpy on Mono DLLs instead.')
    return {'game_root':str(src),'metadata':metadata[:12],'native_binary':native[:12],'archive':False}


def recover(source: Path,out:Path,*,cpp2il:str|None=None,install:bool=False,ilspy:str|None=None,
            decompile:bool=True,install_ilspy:bool=False,timeout:int=1800,max_dlls:int=24) -> dict[str,Any]:
    src=normalized_source(source)
    out=out.expanduser().resolve()
    if src==out or src in out.parents or out in src.parents:
        raise ValueError('Output and original game source must not overlap')
    if out.exists() and any(out.iterdir()):raise ValueError('Output directory must be empty: '+str(out))
    if not (1<=timeout<=7200):raise ValueError('timeout must be 1..7200 seconds')
    if not (1<=max_dlls<=100):raise ValueError('max_dlls must be 1..100')
    identified=inspect_il2cpp(src)
    exe=resolve_cpp2il(cpp2il,install=install)
    probe=subprocess.run([exe,'--list-output-formats'],capture_output=True,text=True,timeout=90,stdin=subprocess.DEVNULL)
    formats=(probe.stdout or '')+'\n'+(probe.stderr or '')
    if probe.returncode!=0 or 'dll_il_recovery' not in formats.lower():
        raise RuntimeError('Cpp2IL must support --output-as dll_il_recovery (development rewrite). Install pinned development CLI; release 2022.0.7 is not sufficient. '+formats[-500:])
    out.mkdir(parents=True,exist_ok=True)
    recovered=out/'cpp2il_dlls'
    recovered.mkdir(parents=True,exist_ok=True)
    cmd=[exe,'--game-path',str(src),'--output-as','dll_il_recovery','--output-to',str(recovered)]
    # run with stdin closed, never run the game .exe, prevent unknown executable injection
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,stdin=subprocess.DEVNULL)
    log=out/'cpp2il_output.txt'
    log.write_text((p.stdout or '')[-200000:]+'\n'+(p.stderr or '')[-200000:],encoding='utf-8')
    if p.returncode!=0:
        raise RuntimeError('Cpp2IL failed. See '+str(log)+': '+(p.stderr or p.stdout)[-900:])
    dlls=sorted(p for p in recovered.rglob('*.dll') if p.is_file() and not p.is_symlink())
    if not dlls: raise RuntimeError('Cpp2IL produced no DLLs. See '+str(log)+'; cannot infer game code from a resource dump.')
    if len(dlls)>max_dlls:
        raise RuntimeError(f'Cpp2IL produced {len(dlls)} DLLs. Increase --max-dlls to opt into processing them.')
    manifest:dict[str,Any]={
        'tool':'Cpp2IL','tool_source_commit':CPP2IL_COMMIT,'cpp2il_executable':exe,
        'original_game':str(src),'il2cpp':identified,
        'output_mode':'approximate_managed_dll_recovery',
        'dlls':[{'path':str(p.relative_to(out)),'sha256':digest(p),'bytes':p.stat().st_size} for p in dlls],
        'csharp':[],'decompile_errors':[],'gameplay_recovered':False,'playable_html':False,
    }
    if decompile:
        from recover_unity_code import recover as recover_managed
        for index,dll in enumerate(dlls):
            if not dll.name.lower().startswith(('assembly-csharp','assembly-unityscript')):continue
            dest=out/'ilspy_csharp'/f'{index:03}_{dll.stem}'
            try:
                result=recover_managed(dll,dest,ilspy=ilspy,install=install_ilspy,timeout=min(timeout,1800))
                manifest['csharp'].append({'source':str(dll.relative_to(out)),'cs_files':sum(a['cs_files'] for a in result['assemblies']),'folder':str(dest.relative_to(out))})
            except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as ex:
                manifest['decompile_errors'].append({'dll':str(dll.relative_to(out)),'error':str(ex)[:500]})
    (out/'cpp2il_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


def main():
    ap=argparse.ArgumentParser(description='Recover approximate IL2CPP DLLs with Cpp2IL; optional ILSpy C# reading')
    ap.add_argument('source',type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--cpp2il',help='Cpp2IL development CLI executable')
    ap.add_argument('--install-cpp2il',action='store_true',help='Build pinned MIT Cpp2IL from source (needs git + .NET 10)')
    ap.add_argument('--ilspy',help='ILSpyCmd executable for optional DLL -> C# stage')
    ap.add_argument('--install-ilspy',action='store_true',help='Install official ILSpyCmd if missing')
    ap.add_argument('--no-decompile',action='store_true',help='Export approximate managed DLLs without ILSpy')
    ap.add_argument('--timeout',type=int,default=1800)
    ap.add_argument('--max-dlls',type=int,default=24)
    a=ap.parse_args()
    result=recover(a.source,a.out,cpp2il=a.cpp2il,install=a.install_cpp2il,ilspy=a.ilspy,
                   decompile=not a.no_decompile,install_ilspy=a.install_ilspy,timeout=a.timeout,max_dlls=a.max_dlls)
    print(f"Cpp2IL exported {len(result['dlls'])} approximate managed DLLs; ILSpy read {len(result['csharp'])} assemblies. Playable HTML: NOT produced.")

if __name__=='__main__':
    try: main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError,zipfile.BadZipFile) as ex:sys.exit('ERROR: '+str(ex))
