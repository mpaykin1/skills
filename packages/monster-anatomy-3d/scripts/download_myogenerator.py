#!/usr/bin/env python3
"""Download original MyoGeneratorRemix source and prepare installable Blender addon ZIP."""
import argparse
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_TAG = 'v2.0.0'
SOURCE_URL = 'https://codeload.github.com/MiguelDLM/MyoGeneratorRemix/zip/refs/tags/{tag}'
EXPECTED_FILES = ('AddonFolder/__init__.py', 'AddonFolder/blender_manifest.toml', 'AddonFolder/myoGenerator_panel.py', 'LICENSE.md', 'README.md')

def download(tag: str, dest: Path) -> Path:
    if not tag.startswith('v') or not all(c.isalnum() or c in '.-_' for c in tag):
        raise ValueError('Unsafe tag; use a specific upstream release tag, e.g. v2.0.0')
    dest.mkdir(parents=True, exist_ok=True)
    address = SOURCE_URL.format(tag=tag)
    req = urllib.request.Request(address, headers={'User-Agent':'MonsterAnatomy3D/0.1 source fetcher'})
    with urllib.request.urlopen(req, timeout=90) as res:
        data = res.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024: raise ValueError('Unexpectedly large source archive')
    source_file = dest / f'MyoGeneratorRemix-{tag}-source.zip'
    with zipfile.ZipFile(io.BytesIO(data)) as source_zip:
        names=source_zip.namelist()
        def matching(suffix): return next((name for name in names if name.endswith('/'+suffix)),None)
        for name in EXPECTED_FILES:
            if not matching(name): raise RuntimeError('Missing upstream file: '+name)
        payload = {}
        for full in names:
            if '/AddonFolder/' not in full or full.endswith('/'): continue
            local = full.split('/AddonFolder/', 1)[1]
            pp=Path(local)
            if pp.is_absolute() or '..' in pp.parts or not local: raise ValueError('Unsafe upstream ZIP member')
            if local.endswith(('.py', '.toml', '.md', '.txt', '.json')):
                payload['MyoGeneratorRemix/'+local] = source_zip.read(full)
        if 'MyoGeneratorRemix/__init__.py' not in payload: raise RuntimeError('Addon package missing')
        addon_zip = dest / f'MyoGeneratorRemix-{tag}-blender-addon.zip'
        with zipfile.ZipFile(addon_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as out:
            for name, blob in sorted(payload.items()): out.writestr(name,blob)
            for filename in ('LICENSE.md','README.md'):
                out.writestr('upstream-'+filename,source_zip.read(matching(filename)))
    source_file.write_bytes(data)
    print(json.dumps({'source_zip':str(source_file),'blender_addon_zip':str(addon_zip),'addon_files':len(payload),'url':address},indent=2))
    return addon_zip

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--tag',default=DEFAULT_TAG)
    p.add_argument('--dest',type=Path,default=Path('vendor'))
    a=p.parse_args()
    try: download(a.tag, a.dest)
    except Exception as exc:
        print(f'Download failed: {type(exc).__name__}: {exc}',file=sys.stderr); sys.exit(2)
