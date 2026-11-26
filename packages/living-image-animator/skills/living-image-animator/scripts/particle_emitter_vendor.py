#!/usr/bin/env python3
"""Build genuine pinned PixiJS-v8 particle-emitter as browser IIFE using esbuild.

The upstream ESM/CJS artifact imports PixiJS; this explicit Pixi shim shares
window.PIXI v8 rather than bundling another incompatible PixiJS copy. No CDN.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from particle_emitter_bridge import runtime_binary

NAME='@spd789562/particle-emitter'
VERSION='1.0.2'
ESBUILD_VERSION='0.25.12'
class VendorError(ValueError):pass

# Exports used by the genuine upstream Pixi v8 emitter package. These are
# aliases to the already embedded genuine window.PIXI; character art untouched.
PIXI_SHIM=r'''const PIXI=window.PIXI;
if(!PIXI||!PIXI.ParticleContainer)throw new Error('Genuine PixiJS v8 must load before Pixi Particle Emitter');
export const Point=PIXI.Point;
export const Ticker=PIXI.Ticker;
export const Particle=PIXI.Particle;
export const ParticleContainer=PIXI.ParticleContainer;
export const Texture=PIXI.Texture;
export const Color=PIXI.Color;
export const ViewContainer=PIXI.ViewContainer;
export const Bounds=PIXI.Bounds;
export const particleData=PIXI.particleData;
'''

def vendor(destination,npm='npm'):
    exe=shutil.which(npm)
    if not exe:raise VendorError('npm not installed; provide genuine prebuilt --particles-js bundle')
    destination=Path(destination).resolve()
    with tempfile.TemporaryDirectory(prefix='lia_pixi_v8_particles_') as td:
        root=Path(td)
        proc=subprocess.run([exe,'install','--prefix',td,'--ignore-scripts','--no-audit','--no-fund','--save-exact',
                f'{NAME}@{VERSION}',f'esbuild@{ESBUILD_VERSION}'],cwd=td,
                capture_output=True,text=True,timeout=240,check=False)
        if proc.returncode:raise VendorError('Official PixiJS v8 emitter could not be fetched: '+(proc.stderr or proc.stdout)[-850:])
        try:
            manifest=json.loads((root/'node_modules'/'@spd789562'/'particle-emitter'/'package.json').read_text())
            if manifest.get('name')!=NAME or manifest.get('version')!=VERSION or manifest.get('license')!='MIT':
                raise VendorError('Wrong package, version or MIT license')
            shim=root/'pixi-global-shim.mjs';shim.write_text(PIXI_SHIM,'utf8')
            entry=root/'entry.mjs';entry.write_text('import { Emitter } from "@spd789562/particle-emitter";\nwindow.LIA_ParticleEmitter={Emitter};\n','utf8')
            esbuild=root/'node_modules'/'esbuild'/'bin'/'esbuild'
            if not esbuild.is_file():raise VendorError('Pinned esbuild binary was not installed')
            out=root/'particle-emitter-browser.js'
            # esbuild shares PIXI globals through shim, never bundles PixiJS twice.
            run=subprocess.run([str(esbuild),str(entry),'--bundle','--platform=browser',
                    '--format=iife','--target=es2020',f'--alias:pixi.js={shim}',f'--outfile={out}'],
                    cwd=td,capture_output=True,text=True,timeout=90,check=False)
            if run.returncode:raise VendorError('Pinned emitter bundling failed: '+(run.stderr or run.stdout)[-900:])
            payload=out.read_bytes()
            if b'LIA_ParticleEmitter' not in payload or b'Emitter' not in payload or not 6000<=len(payload)<=4_000_000:
                raise VendorError('Compiled browser IIFE missing real emitter export')
        except (OSError,ValueError,KeyError) as exc:
            if isinstance(exc,VendorError):raise
            raise VendorError('Cannot validate genuine emitter source/dependencies: '+str(exc)) from exc
        destination.parent.mkdir(parents=True,exist_ok=True)
        tmp=destination.with_suffix('.tmp');tmp.write_bytes(payload);os.replace(tmp,destination)
        license_source=Path(__file__).resolve().parent.parent/'references'/'LICENSE.v8-particle-emitter.txt'
        if not license_source.is_file():raise VendorError('Original MIT license file missing from plugin')
        destination.with_name('LICENSE.v8-particle-emitter.txt').write_bytes(license_source.read_bytes())
    runtime_binary(destination)
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--npm',default='npm')
    a=p.parse_args();print(vendor(a.out,a.npm))
