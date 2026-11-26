#!/usr/bin/env python3
"""Recover legally accessible Unity assets via AssetRipper 2.0.0's LOCAL HTTP API.

Original AssetRipper source: AssetRipper.GUI.Web/Pages/Commands.cs
Endpoints: POST /LoadFile|/LoadFolder, POST /Export/UnityProject|/Export/PrimaryContent.
This DOES NOT decompile managed game logic or create a playable HTML game.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def auto_executable(explicit=None):
    if explicit: return str(Path(explicit).expanduser().resolve(strict=True))
    if os.environ.get('ASSETRIPPER_EXE'): return str(Path(os.environ['ASSETRIPPER_EXE']).expanduser().resolve(strict=True))
    found=shutil.which('AssetRipper') or shutil.which('assetripper')
    if found: return found
    root=Path.home()/'.cache'/'godot-unity-to-html'/'assetripper'/'2.0.0'
    if root.exists():
        matches=[p for p in root.rglob('*') if p.is_file() and p.name.lower() in ('assetripper','assetripper.exe')]
        if matches:return str(matches[0])
    raise RuntimeError('AssetRipper missing; run install_assetripper.py or specify --ripper')


def free_local_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]


def request(url:str, values=None,timeout=120):
    data=None if values is None else urllib.parse.urlencode(values).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/x-www-form-urlencoded'} if data is not None else {})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        return resp.read(512*1024)


def recover(source:Path,out:Path,exe=None,mode='unity',timeout=1800):
    source=source.expanduser().resolve(strict=True)
    out=out.expanduser().resolve()
    if out==source or source in out.parents or out in source.parents:
        raise ValueError('Output must not overlap input')
    if out.exists() and any(out.iterdir()): raise ValueError('Recovery destination must be empty: '+str(out))
    if mode not in ('unity','primary'): raise ValueError('Invalid recovery mode')
    if source.is_file() and source.suffix.lower() in ('.exe','.app'):
        possible=source.with_name(source.stem+'_Data')
        if possible.is_dir():source=possible
        else:raise ValueError('Unity executable without matching *_Data folder; pass the game folder')
    allowed_extensions={'.assets','.bundle','.unity3d','.sharedassets','.ress','.resource','.dat','.obb'}
    if source.is_file() and source.suffix.lower() not in allowed_extensions:
        raise ValueError('Give a Unity game data directory or supported asset/bundle, not an arbitrary executable')
    executable=auto_executable(exe)
    port=free_local_port()
    url=f'http://127.0.0.1:{port}'
    out.parent.mkdir(parents=True,exist_ok=True)
    log_path=out.parent/'assetripper.log'
    begin=time.monotonic()
    with log_path.open('wb') as log:
        # --headless is official 2.0.0 flag; bind loopback only.
        proc=subprocess.Popen([executable,'--headless','--port',str(port)],stdout=log,stderr=subprocess.STDOUT)
        try:
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(f'AssetRipper stopped before its API became ready. See {log_path}')
                if time.monotonic()-begin>min(timeout,90):
                    raise RuntimeError(f'AssetRipper API startup timed out. See {log_path}')
                try:
                    request(url+'/',timeout=2)
                    break
                except (urllib.error.URLError,TimeoutError):time.sleep(.25)
            source_path=str(source)
            request(url+('/LoadFolder' if source.is_dir() else '/LoadFile'),{'Path':source_path}, timeout=max(20,int(timeout-(time.monotonic()-begin))))
            if proc.poll() is not None:raise RuntimeError('AssetRipper exited during file load')
            endpoint='/Export/UnityProject' if mode=='unity' else '/Export/PrimaryContent'
            request(url+endpoint,{'Path':str(out),'CreateSubfolder':'false'},timeout=max(20,int(timeout-(time.monotonic()-begin))))
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
    if not out.exists() or not any(out.rglob('*')):
        raise RuntimeError('AssetRipper did not export assets; inspect local log: '+str(log_path))
    if mode=='unity' and not (out/'Assets').is_dir():
        raise RuntimeError('Unity project export incomplete: missing Assets/; see '+str(log_path))
    print('Recovered Unity '+mode+' resources:',out)
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--ripper')
    ap.add_argument('--mode',choices=['unity','primary'],default='unity')
    ap.add_argument('--timeout',type=int,default=1800)
    args=ap.parse_args()
    recover(args.source,args.out,exe=args.ripper,mode=args.mode,timeout=args.timeout)

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError,urllib.error.URLError) as e:sys.exit('ERROR: '+str(e))
