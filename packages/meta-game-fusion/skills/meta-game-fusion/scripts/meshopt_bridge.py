#!/usr/bin/env python3
"""Audit the exact GLB bytes copied into a generated game.

Read-only asset inspection; outputs a manifest in the new game project, never in
source games. EXT_meshopt_compression is a *visual* encoding: Rapier remains the
collision authority, Recast remains navigation authority. No false decoding or
compression is performed here; actual encoding is glTF-Transform CLI's meshopt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from gltf_optimize import inspect_glb

SCHEMA = 'meta-game-fusion.meshopt-assets.v1'
SHA = re.compile(r'^[0-9a-f]{64}$')
ASSET = re.compile(r'^/assets/([0-9a-f]{18})\.glb$')
EXT = 'EXT_meshopt_compression'
MAX_BYTES = 128 * 1024 * 1024


def sha256(path: Path) -> str:
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def inspect_asset(project: Path, entry: dict[str, Any]) -> dict[str, Any]:
    url, expected = entry.get('src'), entry.get('asset_sha256')
    if not isinstance(url, str) or not ASSET.fullmatch(url):
        raise ValueError('Invalid approved asset URL')
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise ValueError('Missing approved asset SHA-256')
    if ASSET.fullmatch(url).group(1) != expected[:18]:
        raise ValueError('GLB name does not match asset digest')
    path = project / 'public' / url.lstrip('/')
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to((project / 'public').resolve()):
        raise ValueError('Approved asset missing or unsafe: ' + url)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Asset too large: ' + url)
    if sha256(path) != expected:
        raise ValueError('Approved model changed after export: ' + url)
    meta = inspect_glb(path)
    required = set(meta.get('extensionsRequired') or [])
    used = set(meta.get('extensionsUsed') or [])
    if not required.issubset(used):
        raise ValueError('Required GLB extension not listed as used')
    # A Vite GLTFLoader can decode meshopt, WebP and standard glTF only.
    if required - {EXT, 'EXT_texture_webp', 'KHR_texture_basisu'}:
        raise ValueError('GLB requires unsupported extension: ' + str(required))
    views = meta.get('bufferViews') or []
    if not isinstance(views, list):
        raise ValueError('Invalid GLB bufferViews')
    encoded = 0
    allowed_modes = {'ATTRIBUTES', 'TRIANGLES', 'INDICES'}
    allowed_filters = {'NONE', 'OCTAHEDRAL', 'QUATERNION', 'EXPONENTIAL', 'COLOR'}
    for view in views:
        if not isinstance(view, dict):
            raise ValueError('Invalid GLB bufferView')
        ext = (view.get('extensions') or {}).get(EXT)
        if ext is None:
            continue
        if not isinstance(ext, dict):
            raise ValueError('Invalid meshopt buffer view extension')
        if ext.get('mode') not in allowed_modes or ext.get('filter', 'NONE') not in allowed_filters:
            raise ValueError('Unsupported meshopt mode/filter')
        if any(not isinstance(ext.get(k), int) or ext[k] < (0 if k in ('byteOffset', 'buffer') else 1)
               for k in ('buffer', 'byteOffset', 'byteLength', 'byteStride', 'count')):
            # Buffer index may be 0, all remaining integer fields nonnegative / positive.
            # byteOffset also accepts zero; buffer index is covered as zero or more.
            raise ValueError('Invalid meshopt buffer range')
        encoded += 1
    if encoded and EXT not in used:
        raise ValueError('Undeclared meshopt buffer views')
    if EXT in required and not encoded:
        raise ValueError('Required meshopt extension has no encoded buffer views')
    if entry.get('compression') not in (None,'meshopt' if encoded else 'none'):
        raise ValueError('Model declared incorrect meshopt compression')
    buffers = meta.get('buffers') or []
    for view in views:
        ext = (view.get('extensions') or {}).get(EXT)
        if not ext:
            continue
        if ext['buffer'] >= len(buffers) or not isinstance(buffers[ext['buffer']], dict):
            raise ValueError('Compressed buffer index out of bounds')
        total = buffers[ext['buffer']].get('byteLength')
        if not isinstance(total, int) or ext['byteOffset'] + ext['byteLength'] > total:
            raise ValueError('Compressed buffer range exceeds backing buffer')
    from ktx2_bridge import inspect_textures
    ktx2 = inspect_textures(path, meta)
    return {
        'texture_compression': ktx2['texture_compression'],
        'ktx2_textures': ktx2['ktx2_textures'],
        'src': url, 'source_sha256': entry.get('source_sha256'),
        'asset_sha256': expected, 'bytes': path.stat().st_size,
        'compression': 'meshopt' if encoded else 'none',
        'encoded_buffer_views': encoded, 'extensions_required': sorted(required),
        'decoder': 'meshoptimizer@1.3.0' if encoded else None,
        'scene_id': entry.get('scene_id'), 'license': entry.get('license'),
        'animation_clips': len(entry.get('animation_clips') or []),
        'physics_authority': 'Rapier (NOT visual compressed GLB)',
        'navigation_authority': 'Recast',
        'mesh_bvh_input': 'decoded static render geometry only',
    }


def audit_project(project: Path, world: dict[str, Any]) -> dict[str, Any]:
    if not (project / 'public').is_dir() or (project / 'public').is_symlink():
        raise ValueError('Project public directory missing or unsafe')
    assets = world.get('assets')
    if not isinstance(assets, list):
        raise ValueError('Invalid world assets')
    seen: set[str] = set()
    records = []
    for entry in assets:
        if not isinstance(entry, dict):
            raise ValueError('Malformed world asset')
        inspected = inspect_asset(project, entry)
        if inspected['src'] in seen:
            raise ValueError('Duplicate asset URL in world')
        seen.add(inspected['src'])
        records.append(inspected)
    manifest = {
        'schema': SCHEMA, 'decoder': 'meshoptimizer@1.3.0',
        'source_pipeline': 'Assimp -> glTF-Transform@4.5.1 -> meshoptimizer@1.3.0 -> GLTFLoader',
        'visual_only_compression': True,
        'source_files_immutable': True,
        'number_of_assets': len(records),
        'compressed_assets': sum(r['compression'] == 'meshopt' for r in records),
        'assets': records,
    }
    dest = project / 'public' / 'meshopt-manifest.json'
    if dest.is_symlink():
        raise ValueError('Refusing symlink manifest')
    dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['audit'])
    parser.add_argument('--project', required=True)
    a = parser.parse_args()
    try:
        project = Path(a.project).resolve(strict=True)
        world = json.loads((project / 'public' / 'world.json').read_text(encoding='utf8'))
        manifest = audit_project(project, world)
        print(json.dumps({'assets': manifest['number_of_assets'], 'compressed': manifest['compressed_assets']}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        print('meshopt: ' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
