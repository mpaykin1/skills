#!/usr/bin/env python3
"""Use Khronos glTF-Validator on CPU for final GLB gate. No fake fallbacks.

No report files, input alterations, network calls or GPU requirements.
Official Node package MUST be installed explicitly and be exactly pinned.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent

def main(argv=None):
    parser = argparse.ArgumentParser(description='Official Khronos glTF-Validator CPU integrity gate')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--node', default='', help='Node.js binary; default PATH')
    parser.add_argument('--package-dir', default='', help='Official gltf-validator npm package root')
    parser.add_argument('--strict-warnings', action='store_true', help='Also fail on warnings')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args(argv)
    asset = args.input.expanduser().resolve()
    if not asset.is_file() or asset.suffix.lower() != '.glb':
        parser.error('--input must be an existing .glb')
    if not (5 <= args.timeout <= 3600):
        parser.error('--timeout must be 5..3600 seconds')
    node = args.node or shutil.which('node')
    if not node:
        parser.error('Node.js not installed; Khronos validator requires Node (CPU only)')
    source = HERE / 'gltf_validator_bridge.cjs'
    cmd = [str(node), str(source), '--input', str(asset)]
    if args.package_dir:
        cmd.extend(['--package-dir', str(Path(args.package_dir).expanduser().resolve())])
    if args.strict_warnings:
        cmd.append('--strict-warnings')
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, check=False)
    except subprocess.TimeoutExpired:
        print('[Khronos] Validation timeout; asset not approved', file=sys.stderr)
        return 3
    if done.stderr.strip():
        print(done.stderr.strip()[-2000:], file=sys.stderr)
    if not done.stdout.strip():
        print('[Khronos] No official validation result; asset not approved', file=sys.stderr)
        return 3
    try:
        result = json.loads(done.stdout.strip())
    except json.JSONDecodeError:
        print('[Khronos] Invalid validator response; asset not approved', file=sys.stderr)
        return 3
    if not isinstance(result, dict) or result.get('official') is not True:
        print('[Khronos] Missing official validator provenance', file=sys.stderr)
        return 3
    if done.returncode or not result.get('valid'):
        print('[Khronos] Rejected GLB: ' + json.dumps({k:result.get(k) for k in
          ('errors','warnings','unsupportedRequired','externalResources','firstErrors')},ensure_ascii=False),file=sys.stderr)
        return 3
    print('[Khronos] GLB valid: ' + asset.name +
          '; errors=0, warnings=' + str(result.get('warnings', 0)) +
          '; package=' + str(result.get('validator', '?')))
    if result.get('warnings'):
        print('[Khronos] Warnings remain; rendering and animation still require game inspection')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
