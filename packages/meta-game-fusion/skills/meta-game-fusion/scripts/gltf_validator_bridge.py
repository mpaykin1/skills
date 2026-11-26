#!/usr/bin/env python3
"""Invoke the real Khronos npm validator and verify the generated GLB approval gate.

Never mutate upstream source games. `validate` re-runs official gltf-validator
in a newly generated project, `verify` checks the file hash-bound gate stamp.
A local stamp is NOT evidence of visual quality, ownership or a browser PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

STAMP_SCHEMA = 'meta-game-fusion.gltf-validation.v1'
APPROVED = re.compile(r'^/assets/([a-f0-9]{18})\.glb$')
SHA = re.compile(r'^[a-f0-9]{64}$')


def require_file(path: Path, root: Path, max_size: int) -> Path:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_size:
        raise ValueError(f'Unsafe/oversized file: {path.name}')
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError(f'Escaped project: {path.name}')
    return resolved


def read_json(path: Path, root: Path) -> dict:
    resolved = require_file(path, root, 8 * 1024 * 1024)
    data = json.loads(resolved.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Expected JSON object')
    return data


def verify(project: Path) -> dict:
    root = project / 'public'
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Missing public/ directory')
    world = read_json(root / 'world.json', project)
    stamp = read_json(root / 'gltf-validation-manifest.json', project)
    expected_assets = world.get('assets')
    if not isinstance(expected_assets, list) or not isinstance(stamp.get('assets'), list):
        raise ValueError('Missing world/validator assets')
    if stamp.get('schema') != STAMP_SCHEMA or stamp.get('validator') != '2.0.0-dev.3.10':
        raise ValueError('Unrecognized Khronos validation stamp/version')
    if stamp.get('status') != ('validator-executed' if expected_assets else 'no-GLB-assets-to-validate'):
        raise ValueError('Incorrect validator execution state')
    records = {}
    for record in stamp['assets']:
        if not isinstance(record, dict) or not isinstance(record.get('src'), str):
            raise ValueError('Malformed validator stamp')
        if record['src'] in records:
            raise ValueError('Duplicate validator stamp')
        records[record['src']] = record
    if len(records) != len(expected_assets):
        raise ValueError('Validator stamp model count mismatch')
    for entry in expected_assets:
        if not isinstance(entry, dict):
            raise ValueError('Malformed world asset')
        src, digest = entry.get('src'), entry.get('asset_sha256')
        match = APPROVED.fullmatch(src) if isinstance(src, str) else None
        if not match or not isinstance(digest, str) or not SHA.fullmatch(digest) or match.group(1) != digest[:18]:
            raise ValueError('Asset SHA-256/path mismatch')
        row = records.get(src)
        if not row or row.get('asset_sha256') != digest or row.get('errors') != 0:
            raise ValueError('Approved asset not Khronos-validated')
        asset = require_file(root / src.lstrip('/'), project, 128 * 1024 * 1024)
        with asset.open('rb') as handle:
            actual = hashlib.file_digest(handle, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('GLB changed since Khronos validation')
    return {'status': stamp['status'], 'approved_models': len(records)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'verify'])
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    try:
        project = args.project.expanduser().resolve(strict=True)
        if args.command == 'validate':
            script = require_file(project / 'scripts' / 'validate-assets.mjs', project, 512_000)
            proc = subprocess.run(['node', str(script)], cwd=project, capture_output=True,
                                  text=True, timeout=180, check=False)
            if proc.returncode:
                raise ValueError('Actual Khronos glTF-Validator failed: ' + (proc.stderr or proc.stdout)[-700:])
        print(json.dumps(verify(project), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print('glTF-Validator: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
