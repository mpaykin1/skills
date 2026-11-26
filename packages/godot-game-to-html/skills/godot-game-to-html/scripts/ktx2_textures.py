#!/usr/bin/env python3
"""Non-destructive KTX2 UASTC candidate encoder using official Khronos KTX-Software 5+.

Source PNGs remain authoritative. All output files are separate candidates for
WebGL/Three.js, NOT automatically installed in a Godot/Unity project or GLB.
A real installed `ktx` binary is required (create + validate subcommands).
"""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile

MAGIC = b'\xabKTX 20\xbb\r\n\x1a\n'


def inside(parent: Path, child: Path) -> bool:
    return child == parent or parent in child.parents


def inspect_png(path: Path):
    with Image.open(path) as img:
        img.load()
        if img.format != 'PNG':
            raise ValueError('Not a PNG')
        if img.mode not in ('RGB', 'RGBA'):
            raise ValueError(f'Unsupported source mode {img.mode}; conversion would alter original data')
        width, height = img.size
        if width < 4 or height < 4 or width % 4 or height % 4:
            raise ValueError('KTX2 BasisU textures require width and height divisible by four')
        if max(width, height) > 8192:
            raise ValueError('Texture dimensions exceed safe 8192px limit')
        return {'width': width, 'height': height, 'alpha': img.mode == 'RGBA',
                'mode': img.mode, 'icc_present': bool(img.info.get('icc_profile'))}


def check_ktx2(path: Path, source: dict):
    with path.open('rb') as f:
        data = f.read(80)
    if len(data) < 80 or data[:12] != MAGIC:
        raise ValueError('KTX2 container magic/header invalid')
    width, height = struct.unpack_from('<II', data, 20)
    if (width, height) != (source['width'], source['height']):
        raise ValueError('KTX2 dimensions changed without authorization')


def main():
    p=argparse.ArgumentParser(description='KTX2 UASTC texture candidates from ORIGINAL PNGs, without changing originals')
    p.add_argument('source', type=Path, help='PNG or directory containing PNGs')
    p.add_argument('--out', type=Path, required=True, help='separate output directory')
    p.add_argument('--kind', choices=['color','data','normal'], required=True,
                   help='Color uses sRGB; AO/ORM/normal are linear-data textures')
    p.add_argument('--ktx', default='ktx', help='installed official KTX-Software 5+ CLI')
    p.add_argument('--mipmaps', action='store_true', help='explicit opt-in mipmap generation')
    p.add_argument('--quality', type=int, choices=range(5), metavar='0..4', default=3)
    p.add_argument('--keep-larger', action='store_true',
                   help='keep KTX2 candidates even if larger on disk (might still save GPU memory)')
    p.add_argument('--max-files', type=int, default=512)
    a=p.parse_args()
    source=a.source.expanduser().resolve(strict=True)
    target=a.out.expanduser().resolve()
    if source.is_file():
        if source.suffix.lower() != '.png':
            p.error('Source file must be PNG')
        scope=source.parent
        files=[source]
    elif source.is_dir():
        scope=source
        files=sorted(x for x in source.rglob('*.png') if x.is_file() and not x.is_symlink())
    else:
        p.error('Source must be PNG or directory')
    if inside(scope,target) or inside(target,scope):
        p.error('Output must be a separate disjoint directory, not inside the source directory')
    if not files or len(files) > a.max_files or a.max_files < 1:
        p.error('No PNG files or --max-files threshold exceeded')
    executable=shutil.which(a.ktx) or (str(Path(a.ktx).resolve()) if Path(a.ktx).is_file() else None)
    if not executable:
        raise RuntimeError('Install official Khronos KTX-Software v5+ and provide --ktx /path/to/ktx')
    if subprocess.run([executable,'create','--help'],capture_output=True,timeout=20).returncode != 0:
        raise RuntimeError('Installed KTX tool does not support modern `ktx create` (v5+ required)')
    target.mkdir(parents=True,exist_ok=True)
    records=[]
    for src in files:
        record={'source': str(src.relative_to(scope)), 'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
                'kind':a.kind,'status':'skipped'}
        try:
            spec=inspect_png(src)
            record.update(spec)
            fmt='R8G8B8A8' if spec['alpha'] else 'R8G8B8'
            fmt+='_' + ('SRGB' if a.kind=='color' else 'UNORM')
            tf='srgb' if a.kind=='color' else 'linear'
            primaries='srgb' if a.kind=='color' else 'none'
            with tempfile.TemporaryDirectory(prefix='ktx2-safe-') as tmp:
                produced=Path(tmp)/'candidate.ktx2'
                cmd=[executable,'create','--format',fmt,'--encode','uastc-ldr-4x4',
                     '--uastc-quality',str(a.quality),'--zstd','12',
                     '--assign-tf',tf,'--assign-primaries',primaries,
                     '--assign-texcoord-origin','top-left','--fail-on-color-conversions',
                     '--fail-on-origin-changes']
                if a.mipmaps:cmd+=['--generate-mipmap']
                cmd.extend([str(src),str(produced)])
                encoded=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
                if encoded.returncode:
                    raise RuntimeError('ktx create: '+(encoded.stderr or encoded.stdout)[-700:])
                if not produced.is_file():
                    raise RuntimeError('ktx create produced no texture')
                check_ktx2(produced,spec)
                validated=subprocess.run([executable,'validate','--gltf-basisu',str(produced)],
                                         capture_output=True,text=True,timeout=60)
                if validated.returncode:
                    raise RuntimeError('ktx validate: '+(validated.stderr or validated.stdout)[-700:])
                original_size=src.stat().st_size
                candidate_size=produced.stat().st_size
                record.update({'png_bytes':original_size,'ktx2_bytes':candidate_size,
                               'format':fmt,'codec':'uastc-ldr-4x4','validated_gltf_basisu':True,
                               'mipmaps':a.mipmaps})
                if candidate_size>=original_size and not a.keep_larger:
                    record['reason']='candidate not smaller on disk'
                else:
                    rel=src.relative_to(scope).with_suffix('.ktx2')
                    dst=target/rel
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    if dst.exists():
                        raise RuntimeError('Refusing to replace existing candidate: '+str(dst))
                    os.replace(produced,dst)
                    record.update({'status':'candidate','output':str(rel)})
        except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as err:
            record['reason']=str(err)
        records.append(record)
    manifest=target/'ktx2-candidates.json'
    if manifest.exists():
        raise RuntimeError('Refusing to replace existing KTX2 manifest; choose a new output directory')
    manifest.write_text(json.dumps({'tool':'Khronos KTX-Software 5+','model':'original PNG immutable',
             'application':'manual only after renderer comparison', 'texture_kind':a.kind,
             'textures':records},ensure_ascii=False,indent=2),encoding='utf-8')
    successes=sum(x['status']=='candidate' for x in records)
    print(f'KTX2 validated candidates: {successes}/{len(records)}, output: {target}')
    if not successes:
        print('No smaller candidate found; keep existing original PNGs and WebGL build unchanged')

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError) as e:
        raise SystemExit('ERROR: '+str(e))
