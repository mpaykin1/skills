#!/usr/bin/env python3
"""META GAMES real Sprite Sheet Helper CLI bridge: GLB or actual sprite stack -> directional atlases.

Godot/Unity original GLB tracks and geometry remain authoritative. Approved
stack.json uses the previously installed sprite-in-the-round native GLB export;
PNG four-views use the previously installed four-view carver first.
No fake animation/independent directional illustration is generated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from PIL import Image
from install_upstream import COMMIT, UPSTREAM, resolve

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ROUND = ROOT / 'sprite-in-the-round-bridge' / 'scripts' / 'round_bridge.py'
FOUR = ROOT / 'sprite-stacking-four-views' / 'scripts' / 'views_to_stack.py'
FORMATS = ('spritesheet', 'phaser', 'godot', 'unity', 'zip', 'gif', 'bevy', 'pygame', 'raylib', 'love2d-lua', 'love2d-anim8')
WORKFLOWS = ('topdown-8dir', 'topdown-4dir', 'isometric', 'platformer', 'topdown-1dir',
             'platformer-1dir', 'front-back-2dir', 'three-quarter-4dir', 'three-quarter-8dir',
             'isometric-1dir', 'front-facing', 'profile-1dir', 'diagonal-4dir')


def check_source(path: Path) -> None:
    if path.is_symlink():
        raise ValueError('Symlinked model/manifest is not accepted')
    if not path.is_file():
        raise ValueError('Source must be an approved GLB, stack.json, or four-view PNG')
    if path.suffix.lower() == '.glb':
        with path.open('rb') as f:
            if f.read(4) != b'glTF':
                raise ValueError('Expected glTF binary model')
    elif path.suffix.lower() == '.json':
        doc = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(doc, dict) or not isinstance(doc.get('layers'), list):
            raise ValueError('Expected actual sprite stack.json with layers')
    elif path.suffix.lower() == '.png':
        with Image.open(path) as im:
            if im.format != 'PNG' or im.width * im.height > 16_000_000:
                raise ValueError('Source PNG must be an approved four-view sheet <=16 megapixels')
    else:
        raise ValueError('Supported formats: .glb, stack.json, four-view .png')


def exported_glb(source: Path, out: Path, args: argparse.Namespace) -> Path:
    if source.suffix.lower() == '.glb':
        return source
    if source.suffix.lower() == '.png':
        if not args.four_views:
            raise ValueError('PNG input requires explicit --four-views; never infer 3D from one flat sprite')
        if not FOUR.is_file():
            raise RuntimeError('The first four-view sprite-stacking module is missing')
        carved = out / 'intermediate' / 'fourview'
        cmd = [sys.executable, str(FOUR), str(source), '--out', str(carved),
               '--slices', str(args.slices), '--no-html']
        if args.no_install_upstream:
            cmd.append('--no-install-upstream')
        subprocess.run(cmd, check=True, timeout=600)
        stack = carved / 'stack-data' / 'stack.json'
    else:
        stack = source
    if not ROUND.is_file():
        raise RuntimeError('The previous sprite-in-the-round bridge is missing')
    converter = out / 'intermediate' / 'round'
    cmd = [sys.executable, str(ROUND), str(stack), '--out', str(converter),
           '--no-html', '--dirs', '0']
    if args.no_install_upstream:
        cmd.append('--no-install-upstream')
    subprocess.run(cmd, check=True, timeout=1500)
    glb = converter / 'exports' / 'sprite_stack.glb'
    if not glb.is_file():
        raise RuntimeError('The source contains multiple animation poses or no static GLB. '
                           'Use the original animated GLB directly; never synthesize character motion.')
    return glb


def glb_has_animations(path: Path) -> bool:
    with path.open('rb') as f:
        head = f.read(20)
        if len(head) < 20 or head[:4] != b'glTF' or struct.unpack_from('<I', head, 16)[0] != 0x4E4F534A:
            raise ValueError('Original GLB JSON chunk missing')
        length = struct.unpack_from('<I', head, 12)[0]
        if length > 32 * 1024 * 1024:
            raise ValueError('GLB JSON metadata too large')
        data = json.loads(f.read(length).decode('utf-8'))
        return bool(data.get('animations'))


def run(args: argparse.Namespace) -> Path:
    source = args.source.expanduser()
    if source.is_symlink():
        raise ValueError('Source symlink not allowed')
    source = source.resolve(strict=True)
    out = args.out.expanduser().resolve()
    if out == source or out == source.parent or out in source.parents:
        raise ValueError('Output directory must not overlap original source')
    if source.suffix.lower() == '.json' and (source.parent == out or source.parent in out.parents):
        raise ValueError('Cannot write generated assets inside a source stack directory')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be new and empty; no existing assets are overwritten')
    check_source(source)
    if args.frames is not None and args.frames != 'auto':
        if not args.frames.isdigit() or not 1 <= int(args.frames) <= 64:
            raise ValueError('Use --frames 1..64 or --frames auto')
    if not (1 <= args.fps <= 30) or not (32 <= args.size <= 512):
        raise ValueError('FPS or sprite dimensions out of range')
    if args.margin * 2 >= args.size or not 0 <= args.margin <= 64:
        raise ValueError('Atlas margin must fit inside sprite dimensions')
    if args.workflow not in WORKFLOWS or args.format not in FORMATS:
        raise ValueError('Unknown official workflow or export format')
    if not 4 <= args.slices <= 192:
        raise ValueError('Four-view slicing count out of range')
    exe_root = resolve(args.helper_root, args.no_install_helper)
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js required for the official headless Sprite Sheet Helper CLI')
    out.mkdir(parents=True, exist_ok=True)
    glb = exported_glb(source, out, args)
    sampled_frames = args.frames
    if sampled_frames is None:
        # A static source is never expanded into duplicate fake animation frames.
        sampled_frames = '8' if source.suffix.lower() == '.glb' and glb_has_animations(glb) else '1'
    assets = out / 'atlas'
    assets.mkdir(parents=True, exist_ok=False)
    cmd = [node, str(exe_root/'dist'/'cli'/'index.js'), str(glb),
           '--workflow', args.workflow, '--format', args.format,
           '--frames', str(sampled_frames), '--fps', str(args.fps),
           '--width', str(args.size), '--height', str(args.size),
           '--fit', 'auto', '--fitScope', 'all', '--margin', str(args.margin),
           '--output', str(assets), '--json']
    if args.packed and args.format == 'spritesheet':
        cmd += ['--atlasLayout', 'packed', '--maxAtlasSize', '2048',
                '--atlasPadding', '2', '--atlasBleed', '1', '--multiPage', 'true']
    elif args.packed:
        raise ValueError('--packed currently supports only generic spritesheet format')
    if args.normal_map:
        cmd += ['--normalMap', 'true']
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=900, cwd=exe_root)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Official headless screenshot/atlas export timed out') from exc
    if proc.returncode:
        raise RuntimeError('Official Sprite Sheet Helper export failed: ' + (proc.stderr or proc.stdout)[-2200:])
    try:
        summary = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError('Official CLI did not return its promised machine-readable export summary') from exc
    jobs = summary.get('jobs') if isinstance(summary, dict) else None
    if not isinstance(summary, dict) or summary.get('status') != 'ok' or not isinstance(jobs, list) or not jobs or any(j.get('status') != 'ok' for j in jobs):
        raise RuntimeError('Official CLI failed at least one atlas job')
    actual = [x for x in assets.rglob('*') if x.is_file()]
    if not actual:
        raise RuntimeError('Official CLI reported success but wrote no spritesheet/asset files')
    if args.format == 'spritesheet':
        sheets = [x for x in actual if x.suffix.lower() == '.png']
        if not sheets:
            raise RuntimeError('Spritesheet export contains no PNG atlas')
        for sheet in sheets:
            with Image.open(sheet) as im:
                if im.format != 'PNG' or im.width > 8192 or im.height > 8192:
                    raise RuntimeError('Unusable or oversized atlas PNG')
    # Link source volume/mesh and atlas without modifying input data.
    (out/'atlas-source.json').write_text(json.dumps({
        'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'rendered_glb': str(glb), 'producer': 'Kyonru/sprite-sheet-helper',
        'producer_commit': COMMIT if not args.helper_root else 'EXPLICIT_LOCAL_UPSTREAM',
        'workflow': args.workflow, 'frames_per_clip': sampled_frames,
        'not_gameplay': True, 'original_sources_unchanged': True,
        'note': 'Camera directions and any actual GLB animation are rendered by original CLI; a static volume has no invented moving poses.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('OFFICIAL_ATLAS:', assets)
    return assets


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path, help='Original animated/static GLB, stack.json, or four-views PNG')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--helper-root', help='Existing built checkout containing dist/cli/index.js and dist/index.html')
    p.add_argument('--no-install-helper', action='store_true', help='Fail rather than fetch/build official CLI')
    p.add_argument('--no-install-upstream', action='store_true', help='Fail rather than fetch previous sprite stacking OSS')
    p.add_argument('--four-views', action='store_true', help='For PNG input: use first official four-view carving module')
    p.add_argument('--slices', type=int, default=64)
    p.add_argument('--workflow', choices=WORKFLOWS, default='three-quarter-8dir')
    p.add_argument('--format', choices=FORMATS, default='spritesheet')
    p.add_argument('--frames', default=None, help='1..64; auto follows original GLB clip; default 8 for animated GLB and 1 for static')
    p.add_argument('--fps', type=int, default=12)
    p.add_argument('--size', type=int, default=128)
    p.add_argument('--margin', type=int, default=6)
    p.add_argument('--packed', action='store_true', help='Compact atlas for spritesheet format only')
    p.add_argument('--normal-map', action='store_true', help='Ask official tool to capture aligned normal atlas')
    a = p.parse_args()
    try: run(a)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit('ERROR: ' + str(exc))


if __name__ == '__main__':
    main()
