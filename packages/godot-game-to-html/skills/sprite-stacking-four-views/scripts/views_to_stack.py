#!/usr/bin/env python3
"""Actual danielwh2/sprite-stacking 4-view visual hull -> META GAMES RGBA stack.json.

The original upstream script is invoked at its pinned Git commit; this adapter
only converts its real bottom-first horizontal slice strip into separate PNGs.
Three.js existing volume renderer is reused for the HTML; game logic is untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image

from install_upstream import COMMIT, UPSTREAM, resolve


MAX_PIXEL_BYTES = 128 * 1024 * 1024


def convert(sheet: Path, out: Path, *, slices: int = 64, order: str = 'reading',
            colours: int = 0, shade: float = 0, dark_thresh: int = 0,
            round_: bool = False, side_nose: str = 'left', top_nose: str = 'auto',
            bg_tol: int = 28, upstream_script: str | None = None,
            no_install_upstream: bool = False, html: bool = True,
            no_install_js: bool = False) -> Path:
    if sheet.expanduser().is_symlink():
        raise ValueError('Symlinked source sheet is not accepted')
    sheet = sheet.expanduser().resolve(strict=True)
    out = out.expanduser().resolve()
    if not sheet.is_file() or sheet.suffix.lower() != '.png':
        raise ValueError('Input must be a four-view top/side/front/back PNG sheet')
    if sheet.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Symlinked or >20 MiB input sheet is not accepted')
    if out == sheet or out == sheet.parent or out in sheet.parents:
        raise ValueError('Output must not replace source PNG or its containing directory')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty; refusing to overwrite earlier results')
    if not (4 <= slices <= 192 and 0 <= colours <= 256 and 0 <= shade <= 1 and 0 <= dark_thresh <= 255):
        raise ValueError('Invalid slice/palette/shading limits')
    with Image.open(sheet) as im:
        if im.format != 'PNG' or max(im.size) > 4096 or im.size[0] * im.size[1] > 16_000_000:
            raise ValueError('PNG dimension/pixel budget exceeded')
    upstream = resolve(upstream_script, no_install=no_install_upstream)
    dest = out / 'stack-data'
    dest.mkdir(parents=True, exist_ok=True)
    strip = dest / 'slices-strip.png'
    normals = dest / 'normals-strip.png'
    emissive = dest / 'emissive-strip.png'
    preview = dest / 'turntable-preview.png'
    command = [sys.executable, str(upstream), str(sheet), str(strip),
               '--slices', str(slices), '--order', order,
               '--colours', str(colours), '--shade', str(shade),
               '--dark-thresh', str(dark_thresh), '--bg-tol', str(bg_tol),
               '--side-nose', side_nose, '--top-nose', top_nose,
               '--normals', str(normals), '--emissive', str(emissive),
               '--preview', str(preview)]
    if round_:
        command.append('--round')
    result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=360)
    if result.returncode:
        raise RuntimeError('Official 4-view slicer failed: ' + (result.stderr or result.stdout)[-2000:])
    with Image.open(strip) as im:
        if im.format != 'PNG':
            raise ValueError('Official output is not a PNG')
        width, height = im.size
        if width % slices or width // slices > 512 or height > 512 or height < 1:
            raise ValueError('Slice strip does not satisfy Three.js volume dimensions')
        w = width // slices
        if w * height * slices * 4 > MAX_PIXEL_BYTES:
            raise ValueError('Stack exceeds 128 MiB volume budget')
        volume = im.convert('RGBA')
        # Upstream horizontally concatenates vol[z] with ground slice on left.
        # Its row 0 is +Y (north/top). Our existing renderer flips PNG on import.
        layers_dir = dest / 'layers'
        layers_dir.mkdir()
        relative = []
        count = 0
        for z in range(slices):
            part = volume.crop((z*w, 0, (z+1)*w, height))
            count += sum(alpha >= 128 for alpha in part.getchannel('A').tobytes())
            name = f'layers/{z:03d}.png'
            part.save(dest / name, optimize=True)
            relative.append(name)
    if count == 0:
        raise ValueError('Upstream carved an empty volume; verify four aligned views')
    stack = {
        'format': 'sprite-stacking-grunge/1',
        'source': str(sheet),
        'source_sha256': hashlib.sha256(sheet.read_bytes()).hexdigest(),
        'source_type': 'four-view-orthographic-sheet',
        'carving': 'four silhouette intersection; missing sides estimated, not original geometry',
        'carver': 'danielwh2/sprite-stacking',
        'carver_repository': UPSTREAM,
        'carver_commit': COMMIT if not upstream_script else 'EXPLICIT_LOCAL_SCRIPT',
        'layers': relative,
        'spacing': [1.0, 1.0, 1.0],
        'pivot': [0.0, 0.0, 0.0],
        'size': 384,
        'axes': 'X right, Y forward (upper image row), Z up; first slice is lowest',
        'dimensions': [w, height, slices],
        'occupied_voxels': count,
        'normal_candidates': 'normals-strip.png',
        'emissive_candidates': 'emissive-strip.png',
        'not_gameplay': True,
        'note': 'Visual-hull estimate from 4 artworks; no guaranteed unseen structure or exact colors.'
    }
    manifest = dest / 'stack.json'
    manifest.write_text(json.dumps(stack, ensure_ascii=False, indent=2), encoding='utf-8')
    if html:
        renderer = Path(__file__).resolve().parents[2] / 'sprite-stacking-priority' / 'scripts' / 'stack_to_html.py'
        if not renderer.is_file():
            raise RuntimeError('META GAMES existing Three.js volume renderer is not installed')
        command = [sys.executable, str(renderer), str(manifest),
                   '--out', str(out / 'sprite-stacking.html')]
        if no_install_js:
            command.append('--no-install')
        subprocess.run(command, check=True, timeout=540)
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description='Four authored orthographic views → real PNG sprite stack → optional Three.js HTML')
    p.add_argument('source', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--slices', type=int, default=64)
    p.add_argument('--order', choices=('auto', 'reading'), default='reading')
    p.add_argument('--colours', type=int, default=0)
    p.add_argument('--shade', type=float, default=0)
    p.add_argument('--dark-thresh', type=int, default=0)
    p.add_argument('--bg-tol', type=int, default=28)
    p.add_argument('--round', action='store_true')
    p.add_argument('--side-nose', choices=('left', 'right'), default='left')
    p.add_argument('--top-nose', choices=('auto', 'up', 'down'), default='auto')
    p.add_argument('--upstream-script', help='Official locally installed views_to_slices.py')
    p.add_argument('--no-install-upstream', action='store_true')
    p.add_argument('--no-html', action='store_true')
    p.add_argument('--no-install-js', action='store_true')
    a = p.parse_args()
    meta = convert(a.source, a.out, slices=a.slices, order=a.order, colours=a.colours,
                   shade=a.shade, dark_thresh=a.dark_thresh, bg_tol=a.bg_tol,
                   round_=a.round, side_nose=a.side_nose, top_nose=a.top_nose,
                   upstream_script=a.upstream_script, no_install_upstream=a.no_install_upstream,
                   html=not a.no_html, no_install_js=a.no_install_js)
    print('META GAMES stack:', meta)
    if not a.no_html:
        print('Autonomous volume HTML:', a.out / 'sprite-stacking.html')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        sys.exit('ERROR: ' + str(exc))
