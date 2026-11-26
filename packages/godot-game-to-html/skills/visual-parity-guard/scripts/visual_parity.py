#!/usr/bin/env python3
"""Original screenshot → Pixelmatch visual fidelity gate → optional original-GLB HTML.

The screenshots must be captured independently in the real target renderer
with matched camera/time/viewports. This adapter cannot invent or capture them.
No original project assets or existing HTML exports are modified.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
SKILL=HERE.parent
ROOT=SKILL.parent
THREE=ROOT/'three-glb-visual-runtime'/'scripts'/'three_glb_to_html.py'
GLTF_GUARD=ROOT/'gltf-asset-guard'/'scripts'/'validate-glb.mjs'

def stage_node(cache:Path,no_install:bool)->Path:
    cache.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((SKILL/'package.json').read_text(encoding='utf-8'))
    package=cache/'package.json'
    if not package.exists() or json.loads(package.read_text(encoding='utf-8'))!=cfg:
        package.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    script=cache/'compare-screenshots.mjs'
    shutil.copy2(HERE/script.name,script)
    missing=[]
    for name,version in cfg['dependencies'].items():
        meta=cache/'node_modules'/name/'package.json'
        if not meta.is_file() or json.loads(meta.read_text(encoding='utf-8')).get('version')!=version:
            missing.append(name)
    if missing:
        if no_install:
            raise RuntimeError('Pinned Pixelmatch/pngjs dependencies not cached; cannot assert visual parity')
        npm=shutil.which('npm')
        if not npm:raise RuntimeError('npm required for installing official pinned Pixelmatch/pngjs dependencies')
        subprocess.run([npm,'install','--prefix',str(cache),'--ignore-scripts','--no-audit','--no-fund'],check=True,timeout=360)
    for name,version in cfg['dependencies'].items():
        meta=cache/'node_modules'/name/'package.json'
        if not meta.is_file() or json.loads(meta.read_text(encoding='utf-8'))['version']!=version:
            raise RuntimeError(f'Pinned package mismatch: {name} {version}')
    return script

def main():
    p=argparse.ArgumentParser(description='Optional visual parity gate for original Godot/Unity/GLB screenshots')
    p.add_argument('--baseline',type=Path,required=True,help='Original aligned PNG screenshot or folder')
    p.add_argument('--candidate',type=Path,required=True,help='Optimized aligned PNG screenshot or folder')
    p.add_argument('--max-ratio',type=float,default=.03,help='Max changed-pixel fraction (0..1), default 0.03')
    p.add_argument('--threshold',type=float,default=.10,help='Per-pixel perceptual color tolerance (0..1)')
    p.add_argument('--include-aa',action='store_true')
    p.add_argument('--diff-dir',type=Path,help='Optional output separate from screenshot folders')
    p.add_argument('--original-glb',type=Path,help='Original self-contained GLB for additional Khronos validation')
    p.add_argument('--optimized-glb',type=Path,help='Candidate GLB for optional Three.js preview packaging')
    p.add_argument('--html-out',type=Path,help='Build offline Three.js visual HTML ONLY after parity PASS')
    p.add_argument('--no-install',action='store_true',help='Require locally installed/cached npm dependencies')
    p.add_argument('--node',default=None)
    a=p.parse_args()
    if (a.original_glb is None)!=(a.optimized_glb is None):p.error('Use both --original-glb and --optimized-glb')
    if a.html_out and not a.optimized_glb:p.error('--html-out requires --optimized-glb')
    if a.html_out and a.html_out.exists():p.error('Refusing to overwrite an existing HTML')
    node=a.node or shutil.which('node')
    if not node:raise RuntimeError('Node.js is required at build time')
    cache=Path.home()/'.cache'/'meta-games-visual-parity'/'pixelmatch-8.0.0'
    script=stage_node(cache,a.no_install)
    cmd=[node,str(script),'--baseline',str(a.baseline),'--candidate',str(a.candidate),
         '--max-ratio',str(a.max_ratio),'--threshold',str(a.threshold)]
    if a.include_aa:cmd.append('--include-aa')
    if a.diff_dir:cmd+=['--diff-dir',str(a.diff_dir)]
    # Gate BEFORE packaging; subprocess failure leaves existing game/export untouched.
    subprocess.run(cmd,check=True,timeout=300)
    if a.original_glb:
        if not THREE.is_file() or not GLTF_GUARD.is_file():
            raise RuntimeError('Original Three.js / Khronos glTF Validator modules missing')
        sys.path.insert(0,str(THREE.parent))
        from three_glb_to_html import prepare_cache
        gltf_cache=prepare_cache(a.no_install)
        guard=gltf_cache/'validate-glb.mjs'
        if not guard.exists():
            raise RuntimeError('Khronos GLB validator absent in local build cache')
        subprocess.run([node,str(guard),str(a.original_glb),'--compare',str(a.optimized_glb)],check=True,timeout=300)
    if a.html_out:
        subprocess.run([sys.executable,str(THREE),str(a.optimized_glb),'--out',str(a.html_out),
                        *(['--no-install'] if a.no_install else [])],check=True,timeout=600)
        print('VISUAL HTML (NOT gameplay):',a.html_out)

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as e:
        sys.exit('ERROR: '+str(e))
