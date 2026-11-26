#!/usr/bin/env python3
"""Original GLB -> offline HTML using a locally bundled Three.js runtime.

Unity source project -> GLB (via existing UnityGLTF module) -> offline visual HTML.
No recovered gameplay is claimed; native original-engine WebGL is authoritative.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ENGINE = HERE.parent.parent / 'godot-game-to-html' / 'scripts'
GUARD = HERE.parent.parent / 'gltf-asset-guard' / 'scripts' / 'validate-glb.mjs'
VERSION = '0.187.0'
DEPS = [('three', VERSION), ('esbuild', '0.25.5'), ('gltf-validator', '2.0.0-dev.3.10')]


def prepare_cache(no_install: bool) -> Path:
    cache = Path.home() / '.cache' / 'meta-original-three' / VERSION
    cache.mkdir(parents=True, exist_ok=True)
    config = json.loads((SKILL / 'package.json').read_text(encoding='utf-8'))
    cfg_path = cache / 'package.json'
    if not cfg_path.exists() or json.loads(cfg_path.read_text(encoding='utf-8')) != config:
        cfg_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    for name in ('build-three-html.mjs', 'visual-runtime.mjs', 'basis-apache-2.0.txt'):
        shutil.copy2(HERE / name, cache / name)
    if not GUARD.is_file():
        raise RuntimeError('Khronos glTF guard missing from the installed plugin')
    shutil.copy2(GUARD, cache / 'validate-glb.mjs')
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node:
        raise RuntimeError('Node.js required to validate and bundle original GLB assets')

    def is_complete() -> bool:
        for name, version in DEPS:
            pkg = cache / 'node_modules' / name / 'package.json'
            if not pkg.is_file():return False
            try:
                if json.loads(pkg.read_text(encoding='utf-8'))['version'] != version:return False
            except (ValueError,KeyError):return False
        return True

    if not is_complete():
        if no_install:
            raise RuntimeError('Pinned Three.js/esbuild/glTF Validator missing; allow installation or populate cache')
        if not npm:
            raise RuntimeError('npm required to install pinned JS dependencies into isolated cache')
        subprocess.run([npm,'install','--prefix',str(cache),'--no-audit','--no-fund','--ignore-scripts=false'],
                       check=True,timeout=360)
    if not is_complete():
        raise RuntimeError('Pinned JS dependencies mismatch: refusing unvalidated GLB build')
    if not (cache/'node_modules'/'three'/'examples'/'jsm'/'libs'/'basis'/'basis_transcoder.wasm').is_file():
        raise RuntimeError('Pinned Three.js package lacks Basis Universal transcoder')
    return cache


def glbs_from_source(source: Path, out: Path, unity: str | None, all_scenes: bool) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() != '.glb':
            raise ValueError('Only original .glb accepted; for .gltf convert with glTF-Transform first')
        return [source]
    if (source/'Assets').is_dir() and (source/'ProjectSettings'/'ProjectVersion.txt').is_file():
        exporter = ENGINE / 'export_unity_glb.py'
        if not exporter.is_file():
            raise RuntimeError('UnityGLTF module not found in parent Godot/Unity skill')
        cmd = [sys.executable, str(exporter), str(source), '--out', str(out/'unitygltf_source')]
        if unity: cmd.extend(['--unity', unity])
        if all_scenes: cmd.append('--all-scenes')
        subprocess.run(cmd, check=True)
        result = sorted((out/'unitygltf_source'/'glb_scenes').glob('*.glb'))
    else:
        result = sorted(source.rglob('*.glb'))
    if not result:
        raise ValueError('No GLB found: supply a .glb or an original Unity project with editor installed')
    if len(result) > 100:
        raise ValueError('Too many GLB files (>100); choose a scene or smaller directory')
    return result


def run() -> None:
    p=argparse.ArgumentParser(description='Original UnityGLTF/Godot GLB -> offline Three.js HTML visual scene (NOT gameplay)')
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path,required=True,help='output HTML file for one GLB; output directory for multiple')
    p.add_argument('--unity',help='Unity Editor executable when source is a Unity project')
    p.add_argument('--all-scenes',action='store_true')
    p.add_argument('--no-install',action='store_true',help='do not invoke npm: require cached exact dependencies')
    p.add_argument('--force',action='store_true',help='Allow replacement of an existing output HTML')
    p.add_argument('--ktx-manifest',type=Path,help='Optional ktx2-candidates.json to embed SHA-matched KTX2 copies with source PNG fallback')
    args=p.parse_args()
    source=args.source.expanduser().resolve(strict=True)
    out=args.out.expanduser().resolve()
    if source.is_dir() and (source==out or source in out.parents or out in source.parents):
        raise ValueError('Output must be outside the input tree to protect original game assets')
    if source.is_file() and source==out:
        raise ValueError('Do not overwrite original GLB')
    paths=glbs_from_source(source,out,args.unity,args.all_scenes)
    cache=prepare_cache(args.no_install)
    multiple=len(paths)>1
    if multiple and out.suffix:
        raise ValueError('For multiple GLBs, --out must be a directory')
    for i, glb in enumerate(paths):
        target=out/(f'{i:03d}-{glb.stem}.html') if multiple or not out.suffix else out
        if not multiple and not out.suffix:
            target=out/(glb.stem+'.html')
        if target.exists() and not args.force:
            raise ValueError(f'Output already exists; pass --force to replace: {target}')
        # Retain all Khronos glTF validation; only a preinstalled Basis decoder
        # authorizes KHR_texture_basisu in this offline visual runtime.
        with tempfile.TemporaryDirectory(prefix='original-ktx2-glb-') as temp:
            candidate=glb
            if args.ktx_manifest:
                candidate=Path(temp)/(glb.stem+'-basis-candidate.glb')
                link=HERE/'embed_ktx2_glb.py'
                subprocess.run([sys.executable,str(link),str(glb),'--manifest',str(args.ktx_manifest),
                                '--out',str(candidate)],check=True,timeout=120)
            subprocess.run(['node',str(cache/'validate-glb.mjs'),str(candidate),
                            '--browser-bridge','--offline-basis'],check=True,timeout=180)
            title=glb.stem.replace('_',' ').replace('-',' ')
            subprocess.run(['node',str(cache/'build-three-html.mjs'),str(candidate),str(target),title],check=True,timeout=240)
            print('Original visual-only Khronos-validated HTML:',target)

if __name__=='__main__':
    try: run()
    except (ValueError,RuntimeError,OSError,subprocess.SubprocessError) as exc:
        sys.exit('ERROR: '+str(exc))
