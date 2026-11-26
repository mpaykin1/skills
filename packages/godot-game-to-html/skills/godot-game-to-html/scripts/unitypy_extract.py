#!/usr/bin/env python3
"""UnityPy 1.25.4 asset extraction for original Unity resource fidelity.

This is intentionally independent of AssetRipper, not a decompiler of game logic.
Safely creates sprites/textures PNG, mesh OBJ, audio WAV, text, font files;
records source provenance and Unity object identifiers for later scene matching.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

VERSION = '1.25.4'
INPUT_EXT = {'.assets', '.bundle', '.unity3d', '.assetbundle', '.unityweb', '.dat', '.sharedassets'}
INCLUDE_NAMES = {'globalgamemanagers', 'resources.assets', 'sharedassets0.assets'}
TYPES = {'Texture2D', 'Sprite', 'Mesh', 'AudioClip', 'TextAsset', 'Font', 'MonoBehaviour'}


def safe_component(value: Any, limit: int = 70) -> str:
    value = re.sub(r'[^\w .\-]+', '_', str(value), flags=re.UNICODE)
    value = value.strip(' ._')
    return (value[:limit].rstrip(' ._') or 'unnamed')


def inputs(source: Path, max_files: int, max_input_mb: int) -> list[Path]:
    source = source.expanduser().resolve(strict=True)
    if source.is_file():
        candidates = [source]
    elif source.is_dir():
        candidates = []
        for p in sorted(source.rglob('*')):
            if p.is_symlink():
                raise ValueError('Symlink inside input rejected: ' + str(p))
            if p.is_file() and (p.suffix.lower() in INPUT_EXT or p.name.lower() in INCLUDE_NAMES or re.fullmatch(r'level\d+', p.name.lower())):
                candidates.append(p)
    else:
        raise ValueError('Expected file or directory: ' + str(source))
    if not candidates:
        raise ValueError('No Unity asset/bundle files found; pass a .assets, .bundle, .unity3d or Unity *_Data folder')
    if len(candidates) > max_files:
        raise ValueError(f'{len(candidates)} files exceeds --max-files={max_files}')
    for p in candidates:
        if p.is_symlink():
            raise ValueError('Symlink input rejected: ' + str(p))
        if p.stat().st_size > max_input_mb * 1024 * 1024:
            raise ValueError(f'Input too large ({p.name}); raise --max-input-mb to opt in')
    return candidates


def json_safe(value: Any, depth: int = 0) -> Any:
    """Bounded representation; never silently treat serialized state as game code."""
    if depth > 7:
        return '<max depth>'
    if value is None or isinstance(value, (bool, int, float, str)):
        return value[:8192] if isinstance(value, str) else value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f'<binary {len(value)} bytes>'
    if isinstance(value, (list, tuple)):
        return [json_safe(v, depth + 1) for v in value[:300]]
    if isinstance(value, dict):
        return {str(k)[:120]: json_safe(v, depth + 1) for k, v in list(value.items())[:300]}
    return str(value)[:512]


def extract(source: Path, out: Path, *, max_files: int = 1000,
            max_input_mb: int = 512, max_assets: int = 20000,
            max_total_mb: int = 2048, include_mono: bool = False) -> dict:
    import UnityPy

    if UnityPy.__version__ != VERSION:
        raise RuntimeError(f'Requires UnityPy=={VERSION}, found {UnityPy.__version__}. Run install_unitypy.py')

    source = source.expanduser().resolve(strict=True)
    out = out.expanduser().resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError('Output must be outside original input directory')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty: ' + str(out))
    paths = inputs(source, max_files, max_input_mb)
    out.mkdir(parents=True, exist_ok=True)
    result = {'extractor': 'UnityPy', 'version': VERSION,
              'source': str(source), 'items': [], 'errors': [], 'skipped': Counter(),
              'count_by_type': Counter(), 'bytes_written': 0}
    used = 0
    ceiling = max_total_mb * 1024 * 1024

    def save_asset(relative: Path, raw: bytes) -> str:
        nonlocal used
        if used + len(raw) > ceiling:
            raise RuntimeError('Export exceeds --max-total-mb; adjust limit if required')
        dest = out / relative
        if not dest.resolve().is_relative_to(out):
            raise ValueError('Unsafe output path')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        used += len(raw)
        return relative.as_posix()

    for path in paths:
        key = str(path.relative_to(source)) if source.is_dir() else path.name
        prefix = hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]
        try:
            # Keeping a file handle open is required for deferred asset streams.
            with path.open('rb') as fp:
                env = UnityPy.load(fp)
                for obj in env.objects:
                    if len(result['items']) >= max_assets:
                        raise RuntimeError('Export exceeds --max-assets')
                    kind = obj.type.name
                    if kind not in TYPES or (kind == 'MonoBehaviour' and not include_mono):
                        result['skipped'][kind] += 1
                        continue
                    path_id = str(getattr(obj, 'path_id', getattr(obj, 'm_PathID', '0')))
                    try:
                        data = obj.parse_as_object()
                        name = safe_component(getattr(data, 'm_Name', kind))
                        ident = f'{prefix}_{safe_component(path_id,30)}_{name}'
                        locations: list[str] = []
                        if kind in ('Texture2D', 'Sprite'):
                            import io
                            buf = io.BytesIO()
                            data.image.save(buf, 'PNG')
                            locations.append(save_asset(Path('textures' if kind == 'Texture2D' else 'sprites') / (ident + '.png'), buf.getvalue()))
                        elif kind == 'Mesh':
                            mesh_text = data.export()
                            locations.append(save_asset(Path('meshes') / (ident + '.obj'), mesh_text.encode('utf-8')))
                        elif kind == 'AudioClip':
                            for index, (sample_name, wav) in enumerate(data.samples.items()):
                                label = safe_component(sample_name, 35)
                                locations.append(save_asset(Path('audio') / f'{ident}_{index:03}_{label}.wav', wav))
                        elif kind == 'TextAsset':
                            payload = data.m_Script
                            if isinstance(payload, str):
                                payload = payload.encode('utf-8', 'surrogateescape')
                            else:
                                payload = bytes(payload)
                            locations.append(save_asset(Path('text') / (ident + '.bin'), payload))
                        elif kind == 'Font':
                            raw = bytes(data.m_FontData)
                            if raw:
                                ext = '.otf' if raw.startswith(b'OTTO') else '.ttf'
                                locations.append(save_asset(Path('fonts') / (ident + ext), raw))
                        elif kind == 'MonoBehaviour':
                            dictionary = obj.parse_as_dict()
                            content = json.dumps(json_safe(dictionary), ensure_ascii=False, indent=2).encode('utf-8')
                            locations.append(save_asset(Path('serialized_states') / (ident + '.json'), content))
                        if locations:
                            result['items'].append({'kind': kind, 'name': name, 'path_id': path_id,
                                                    'source_file': key, 'files': locations})
                            result['count_by_type'][kind] += 1
                    except Exception as ex:
                        result['errors'].append({'source_file': key, 'path_id': path_id,
                                                 'kind': kind, 'error': str(ex)[:500]})
        except RuntimeError:
            raise
        except Exception as ex:
            result['errors'].append({'source_file': key, 'error': str(ex)[:500]})
    result['bytes_written'] = used
    result['count_by_type'] = dict(result['count_by_type'])
    result['skipped'] = dict(result['skipped'])
    (out / 'unitypy_manifest.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    if not result['items']:
        raise RuntimeError('UnityPy extracted no supported original assets; inspect unitypy_manifest.json')
    return result


def main():
    ap = argparse.ArgumentParser(description='UnityPy resource extractor (CPU, no Unity Editor)')
    ap.add_argument('source', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--max-files', type=int, default=1000)
    ap.add_argument('--max-input-mb', type=int, default=512)
    ap.add_argument('--max-assets', type=int, default=20000)
    ap.add_argument('--max-total-mb', type=int, default=2048)
    ap.add_argument('--include-mono', action='store_true', help='Export serialized MonoBehaviour values; not executable C# code')
    a = ap.parse_args()
    result = extract(a.source, a.out, max_files=a.max_files, max_input_mb=a.max_input_mb,
                     max_assets=a.max_assets, max_total_mb=a.max_total_mb, include_mono=a.include_mono)
    print(f"UnityPy exported {len(result['items'])} assets ({result['bytes_written']} bytes) to {a.out}")
    if result['errors']:
        print(f"Skipped damaged or unsupported objects: {len(result['errors'])}", file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, ImportError) as e:
        sys.exit('ERROR: ' + str(e))
