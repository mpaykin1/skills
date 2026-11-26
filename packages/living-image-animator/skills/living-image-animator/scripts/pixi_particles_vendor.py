#!/usr/bin/env python3
"""Install real pixi-v8-particles@0.1.3 and build a browser-global PixiJS v8 addon.

No CDN, no fallback surrogate particles, no invented JS runtime. This needs npm
access once during build, or the exact compiled output supplied by the author.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PACKAGE='pixi-v8-particles@0.1.3'
ESBUILD='esbuild@0.25.12'
PIXI='pixi.js@8.23.0'

class ParticleVendorError(RuntimeError):pass

def vendor(destination:Path,npm='npm')->Path:
    exe=shutil.which(npm)
    if not exe: raise ParticleVendorError('npm missing; provide --particles-js built from authentic pixi-v8-particles v0.1.3')
    destination=Path(destination).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix='lia_pixiv8_particles_') as tmp:
        root=Path(tmp);root.joinpath('package.json').write_text('{"name":"lia-particles-vendor","private":true,"version":"0.0.0"}',encoding='utf8')
        cmd=[exe,'install','--no-audit','--no-fund','--ignore-scripts','--no-package-lock',PACKAGE,ESBUILD,PIXI]
        p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=240,check=False)
        if p.returncode:raise ParticleVendorError('Cannot fetch official PixiJS 8 particle dependency: '+(p.stderr or p.stdout)[-950:])
        meta=json.loads((root/'node_modules/pixi-v8-particles/package.json').read_text('utf8'))
        if (meta.get('name'),meta.get('version'),meta.get('license'))!=('pixi-v8-particles','0.1.3','MIT'):
            raise ParticleVendorError('Downloaded library identity/version/license mismatch')
        if '8' not in meta.get('peerDependencies',{}).get('pixi.js',''):
            raise ParticleVendorError('Particle runtime has no PixiJS v8 peer dependency')
        # Externally bundled PixiJS 8 is already present in the owning HTML.
        # Never link a second Pixi instance: feed a virtual module referencing
        # the browser's existing window.PIXI and IIFE-wrap the real particle lib.
        (root/'lia-entry.mjs').write_text('''import { Emitter, registerAllBehaviors } from 'pixi-v8-particles';\nexport { Emitter, registerAllBehaviors };\n''',encoding='utf8')
        (root/'build.cjs').write_text(r'''const esbuild=require('esbuild');
const shim=`const P=window.PIXI;if(!P||!P.Application)throw new Error('PixiJS 8 must initialize before particles');
${['Container','Point','Ticker','Texture','Sprite','ParticleContainer','Particle','Rectangle','Matrix','Color','Assets','Graphics','Application','RenderTexture','TextureSource','ImageSource','ObservablePoint','BLEND_MODES','SCALE_MODES','ALPHA_MODES'].map(n=>`export const ${n}=P.${n};`).join('\n')}`;
esbuild.build({entryPoints:['lia-entry.mjs'],bundle:true,format:'iife',globalName:'LIA_Particles',platform:'browser',target:'es2020',minify:true,legalComments:'inline',outfile:'dist/pixi-v8-particles.iife.js',plugins:[{name:'reuse-global-pixi',setup(build){build.onResolve({filter:/^pixi\.js$/},()=>({path:'pixi-shim',namespace:'pixi-global'}));build.onLoad({filter:/.*/,namespace:'pixi-global'},()=>({contents:shim,loader:'js'}));}}]}).catch(e=>{console.error(e);process.exitCode=1;});
''',encoding='utf8')
        build=root/'build.cjs'
        proc=subprocess.run(['node',str(build)],cwd=root,capture_output=True,text=True,timeout=90,check=False)
        generated=root/'dist/pixi-v8-particles.iife.js'
        if proc.returncode or not generated.is_file():
            raise ParticleVendorError('PixiJS particle runtime bundling failed: '+(proc.stderr or proc.stdout)[-1500:])
        raw=generated.read_bytes()
        if not 15000<=len(raw)<=2_500_000 or b'LIA_Particles' not in raw or b'Emitter' not in raw:
            raise ParticleVendorError('Invalid compiled real emitter runtime')
        destination.parent.mkdir(parents=True,exist_ok=True)
        tmpfile=destination.with_name(destination.name+'.tmp');tmpfile.write_bytes(raw);os.replace(tmpfile,destination)
        destination.parent.joinpath('pixi-v8-particles.vendor.json').write_text(json.dumps({
            'package':PACKAGE,'pixijs_peer':'8.x','license':'MIT',
            'sha256':hashlib.sha256(raw).hexdigest()},indent=2),'utf8')
        return destination

if __name__=='__main__':
    pa=argparse.ArgumentParser();pa.add_argument('--out',required=True,type=Path);pa.add_argument('--npm',default='npm')
    a=pa.parse_args();print(vendor(a.out,a.npm))
