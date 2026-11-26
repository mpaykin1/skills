#!/usr/bin/env python3
"""Validate approved GLB KHR_texture_basisu images and stage a KTX2 manifest.

This is a strict inspection adapter, not an encoder or transcoder. The real
KTX2 encoding is performed with glTF-Transform CLI + installed KTX-Software.
The browser loads the same GLB using Three.js KTX2Loader and its Basis WASM.
All original game source files are read-only and no asset rights are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any

from gltf_optimize import inspect_glb

SCHEMA = 'meta-game-fusion.ktx2-textures.v1'
KTX2_ID = b'\xabKTX 20\xbb\r\n\x1a\n'
EXT = 'KHR_texture_basisu'
MAX_GLB_BYTES = 128 * 1024 * 1024
SHA = re.compile(r'^[0-9a-f]{64}$')
ASSET = re.compile(r'^/assets/([0-9a-f]{18})\.glb$')


def _chunks(glb: bytes) -> tuple[bytes, bytes]:
    if len(glb) < 20 or len(glb) > MAX_GLB_BYTES:
        raise ValueError('GLB exceeds size limit or is truncated')
    magic, version, length = struct.unpack_from('<4sII', glb)
    if magic != b'glTF' or version != 2 or length != len(glb):
        raise ValueError('Invalid GLB2 header')
    offset = 12
    chunks = []
    while offset < len(glb):
        if offset + 8 > len(glb):
            raise ValueError('Truncated GLB chunk header')
        size, tag = struct.unpack_from('<II', glb, offset)
        offset += 8
        if size % 4 or size > len(glb) - offset:
            raise ValueError('Malformed GLB chunk length')
        chunks.append((tag, glb[offset:offset + size]))
        offset += size
        if len(chunks) > 2:
            raise ValueError('Unexpected GLB chunks')
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError('Missing GLB JSON')
    if len(chunks) == 2 and chunks[1][0] != 0x004E4942:
        raise ValueError('Invalid GLB binary chunk')
    return chunks[0][1], chunks[1][1] if len(chunks) == 2 else b''


def _index(items: list[Any], number: Any, name: str) -> dict[str, Any]:
    if type(number) is not int or not 0 <= number < len(items):
        raise ValueError('Out-of-range ' + name)
    item = items[number]
    if not isinstance(item, dict):
        raise ValueError('Malformed ' + name)
    return item


def inspect_textures(path: Path, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = path.read_bytes()
    _, binary = _chunks(raw)
    meta = meta or inspect_glb(path)
    required, used = set(meta.get('extensionsRequired') or []), set(meta.get('extensionsUsed') or [])
    if not required.issubset(used):
        raise ValueError('Required GLB extension missing in extensionsUsed')
    textures = meta.get('textures') or []
    images = meta.get('images') or []
    views = meta.get('bufferViews') or []
    buffers = meta.get('buffers') or []
    if any(not isinstance(v, list) for v in (textures, images, views, buffers)):
        raise ValueError('Malformed GLB image/texture arrays')
    encoded = []
    seen = set()
    for i, texture in enumerate(textures):
        if not isinstance(texture, dict):
            raise ValueError('Malformed texture')
        ext = (texture.get('extensions') or {}).get(EXT)
        if ext is None:
            continue
        if not isinstance(ext, dict):
            raise ValueError('Malformed texture KHR_texture_basisu')
        image_index = ext.get('source')
        image = _index(images, image_index, 'KTX2 image')
        if image.get('mimeType') != 'image/ktx2':
            raise ValueError('KHR_texture_basisu image is not image/ktx2')
        view = _index(views, image.get('bufferView'), 'KTX2 bufferView')
        buffer_index = view.get('buffer')
        _index(buffers, buffer_index, 'KTX2 backing buffer')
        if buffer_index != 0:
            raise ValueError('GLB KTX2 image references unavailable external buffer')
        start = view.get('byteOffset', 0)
        length = view.get('byteLength')
        if any(type(v) is not int for v in (start, length)) or start < 0 or length < 80 or start + length > len(binary):
            raise ValueError('KTX2 image buffer range invalid')
        header = binary[start:start + 80]
        if header[:12] != KTX2_ID:
            raise ValueError('Invalid KTX2 file identifier')
        width, height, level_count = (struct.unpack_from('<I', header, x)[0] for x in (20, 24, 40))
        if not 1 <= width <= 16384 or not 1 <= height <= 16384 or not 1 <= level_count <= 32:
            raise ValueError('Invalid KTX2 image dimensions/mipmap count')
        encoded.append({'texture': i, 'image': image_index, 'width': width,
                        'height': height, 'mip_levels': level_count})
        seen.add(image_index)
    if encoded and EXT not in used:
        raise ValueError('Undeclared KHR_texture_basisu texture')
    if EXT in required and not encoded:
        raise ValueError('KHR_texture_basisu marked required but no KTX2 images found')
    # No KTX2 files may hide outside declared KHR texture references.
    for i, image in enumerate(images):
        if isinstance(image, dict) and image.get('mimeType') == 'image/ktx2' and i not in seen:
            raise ValueError('Unreferenced KTX2 image in GLB')
    return {'ktx2_images': len(seen), 'ktx2_textures': len(encoded),
            'textures': encoded, 'texture_compression': 'ktx2' if encoded else 'none',
            'ktx2_extension_required': EXT in required}


def audit_project(project: Path, world: dict[str, Any]) -> dict[str, Any]:
    assets = world.get('assets')
    if not isinstance(assets, list):
        raise ValueError('Invalid world assets')
    public = project / 'public'
    if not public.is_dir() or public.is_symlink():
        raise ValueError('Invalid public directory')
    records = []
    for entry in assets:
        if not isinstance(entry, dict):
            raise ValueError('Malformed asset')
        url, expected = entry.get('src'), entry.get('asset_sha256')
        match = ASSET.fullmatch(url) if isinstance(url, str) else None
        if not match or not isinstance(expected, str) or not SHA.fullmatch(expected) or match.group(1) != expected[:18]:
            raise ValueError('Asset URL and SHA-256 mismatch')
        asset = public / url.lstrip('/')
        if asset.is_symlink() or not asset.is_file() or not asset.resolve().is_relative_to(public.resolve()):
            raise ValueError('Invalid approved asset path')
        if asset.stat().st_size > MAX_GLB_BYTES:
            raise ValueError('Approved asset exceeds size budget')
        if hashlib.sha256(asset.read_bytes()).hexdigest() != expected:
            raise ValueError('Asset differs from approved SHA-256')
        details = inspect_textures(asset)
        declared = entry.get('texture_compression')
        if declared not in (None, details['texture_compression']):
            raise ValueError('Incorrect declared texture compression')
        records.append({'src': url, 'asset_sha256': expected, 'license': entry.get('license'),
                        'source_sha256': entry.get('source_sha256'), **details})
    manifest = {'schema': SCHEMA, 'decoder': 'Three.js KTX2Loader + Basis Universal WASM',
                'encoder': 'glTF-Transform@4.5.1 with KTX-Software 4.4.0+',
                'rights_gate': 'ScanCode + per-asset SHA-256 approval',
                'collision_authority': 'Rapier', 'nav_authority': 'Recast',
                'visual_only': True, 'assets': records,
                'compressed_textures': sum(a['ktx2_textures'] for a in records),
                'models_with_ktx2': sum(bool(a['ktx2_textures']) for a in records)}
    destination = public / 'ktx2-manifest.json'
    if destination.is_symlink():
        raise ValueError('Refusing to overwrite symlink')
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
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
        print(json.dumps({'models_with_ktx2': manifest['models_with_ktx2'],
                          'compressed_textures': manifest['compressed_textures']}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, struct.error) as error:
        print('ktx2: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
