#!/usr/bin/env python3
"""CPU-first, non-destructive xatlas UV2 + optional Blender AO + Intel OIDN.

Existing xatlas/Blender stage is preserved. --denoise-ao adds an optional
second CPU-only stage for *baked AO PNG* sidecars, never original textures.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description='Original GLB -> xatlas UV2 + CPU Blender AO -> optional OIDN')
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--blender',default=None,help='Official installed Blender executable')
    p.add_argument('--bake-ao',action='store_true',help='Opt-in Blender Cycles CPU AO PNG maps')
    p.add_argument('--denoise-ao',action='store_true',help='Opt-in Intel OIDN CPU denoise for baked AO only')
    p.add_argument('--oiio-inspect',action='store_true',help='Opt-in OpenImageIO inspection of AO sidecars (no pixel changes)')
    p.add_argument('--oiiotool',help='Installed official OpenImageIO oiiotool executable')
    p.add_argument('--oidn-lib',help='Optional installed official OpenImageDenoise 2 shared library')
    p.add_argument('--oidn-strength',type=float,default=0.7,help='Mix denoised signal; default 0.7')
    p.add_argument('--size',type=int,default=512,help='AO image resolution 64..2048')
    p.add_argument('--samples',type=int,default=24,help='CPU bake samples 1..256')
    p.add_argument('--max-faces',type=int,default=100000)
    p.add_argument('--export-glb',action='store_true',help='Derivative GLB; requires visual comparison')
    a=p.parse_args()
    src=a.source.expanduser().resolve(strict=True)
    if src.suffix.lower() not in ('.glb','.gltf'):
        p.error('Only original .glb/.gltf input supported')
    if not 64<=a.size<=2048 or not 1<=a.samples<=256 or not 1<=a.max_faces<=1000000:
        p.error('Invalid size, samples or max-faces')
    if not 0<=a.oidn_strength<=1:
        p.error('OIDN strength must be 0..1')
    if a.denoise_ao and not a.bake_ao:
        p.error('--denoise-ao requires --bake-ao')
    if a.oiio_inspect and not a.bake_ao:
        p.error('--oiio-inspect requires --bake-ao')
    out=a.out.expanduser().resolve()
    if out==src or src in out.parents or out in src.parents:
        p.error('Output must not include or overwrite the original source file')
    executable=a.blender or shutil.which('blender')
    if not executable or not Path(executable).is_file():
        raise RuntimeError('Blender missing: install official Blender, then use --blender /path/to/blender')
    if a.denoise_ao:
        # Validate optional dependency before a potentially expensive Blender bake.
        from oidn_lightmaps import open_oidn,library_path
        open_oidn(library_path(a.oidn_lib))
    if a.oiio_inspect:
        from oiio_lightmaps import find_tool
        find_tool(a.oiiotool)
    out.mkdir(parents=True,exist_ok=True)
    worker=Path(__file__).with_name('xatlas_blender_worker.py')
    cmd=[str(executable),'--background','--factory-startup','--python',str(worker),'--',
         str(src),'--out',str(out),'--size',str(a.size),'--samples',str(a.samples),'--max-faces',str(a.max_faces)]
    if a.bake_ao:cmd.append('--bake-ao')
    if a.export_glb:cmd.append('--export-glb')
    result=subprocess.run(cmd,timeout=3600,check=False)
    if result.returncode!=0:
        raise RuntimeError('Blender/xatlas failed; original source unchanged')
    manifest=out/'atlas-manifest.json'
    if not manifest.exists() or not (out/'uv2-source.blend').exists():
        raise RuntimeError('Output incomplete; original source remains unchanged')
    if a.denoise_ao:
        ao=out/'ao'
        ao_files=sorted(ao.glob('*_AO.png')) if ao.is_dir() else []
        if not ao_files:
            raise RuntimeError('No AO PNG produced by Blender; cannot run OIDN')
        den_dir=out/'ao-denoised'
        denoise=[sys.executable,str(Path(__file__).with_name('oidn_lightmaps.py')),
                 '--input-dir',str(ao),'--out-dir',str(den_dir),
                 '--strength',str(a.oidn_strength)]
        if a.oidn_lib:denoise += ['--oidn-lib',a.oidn_lib]
        subprocess.run(denoise,check=True,timeout=1200)
        # Additive manifest field; all existing xatlas object records stay intact.
        record=json.loads(manifest.read_text(encoding='utf-8'))
        produced=sorted(x.name for x in den_dir.glob('*_AO_oidn.png'))
        if len(produced)!=len(ao_files):
            raise RuntimeError('OIDN produced incomplete AO sidecars; no original data replaced')
        record['oidn']={'engine':'Intel Open Image Denoise 2 CPU',
                        'filter':'RT LDR (PNG baked AO)',
                        'strength':a.oidn_strength,
                        'original_ao_untouched':True,
                        'files':produced}
        manifest.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print('OIDN AO sidecars:',den_dir)
    if a.oiio_inspect:
        from oiio_lightmaps import find_tool, inspect
        tool=find_tool(a.oiiotool)
        source_files=sorted((out/'ao').glob('*_AO.png'))
        if not source_files:raise RuntimeError('OpenImageIO requested but no Blender AO PNGs found')
        candidates=sorted((out/'ao-denoised').glob('*_AO_oidn.png')) if a.denoise_ao else []
        inspected=[inspect(image,tool) for image in source_files+candidates]
        record=json.loads(manifest.read_text(encoding='utf-8'))
        record['openimageio']={'only_inspection':True,'untouched_original':True,
                               'files':inspected}
        manifest.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print('OpenImageIO verified AO textures:',len(inspected))
    print('XATLAS UV2 RESULT:',out/'uv2-source.blend')
    print('AO MAPS:',out/'ao' if a.bake_ao else 'disabled')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired,subprocess.CalledProcessError) as e:
        sys.exit('ERROR: '+str(e))
