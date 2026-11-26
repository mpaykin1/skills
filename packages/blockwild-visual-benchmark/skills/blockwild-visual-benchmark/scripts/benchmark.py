#!/usr/bin/env python3
"""Compare true rendered game screenshots using the installed official LPIPS.

This adapter does not implement LPIPS itself and never invents a visual quality %.
Copyright (c) 2026 META GAMES. Released under MIT in the containing skill.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise ValueError(message)


def add_shared(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--net', choices=('alex', 'squeeze', 'vgg'), default='alex',
                        help='LPIPS network; default is official recommended alex')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--crop', type=str, help='World-only fixed ROI: x,y,width,height')
    parser.add_argument('--out', type=Path, help='Write metrics JSON (not game files)')


def paths_group(*inputs: Path):
    if all(p.is_file() for p in inputs):
        for p in inputs:
            if p.suffix.lower() != '.png':
                fail(f'Only PNG captures accepted: {p}')
        return [("frame.png", inputs)]
    if not all(p.is_dir() for p in inputs):
        fail('Use either all PNG files or all directories of synchronized PNG captures')
    maps = []
    for directory in inputs:
        mapping = {p.relative_to(directory).as_posix(): p
                   for p in directory.rglob('*.png') if p.is_file()}
        if not mapping:
            fail(f'No PNG captures in {directory}')
        maps.append(mapping)
    expected = set(maps[0])
    for idx, mapping in enumerate(maps[1:], start=2):
        if set(mapping) != expected:
            missing = sorted(expected - set(mapping))[:6]
            extra = sorted(set(mapping) - expected)[:6]
            fail(f'Screenshot names differ for input #{idx}; missing={missing}, extra={extra}')
    return [(name, tuple(m[name] for m in maps)) for name in sorted(expected)]


def crop_tuple(argument: str | None):
    if not argument:
        return None
    try:
        vals = tuple(int(s.strip()) for s in argument.split(','))
    except ValueError:
        fail('Crop must be four integers x,y,width,height')
    if len(vals) != 4 or vals[0] < 0 or vals[1] < 0 or vals[2] < 64 or vals[3] < 64:
        fail('Crop must be x>=0,y>=0,width>=64,height>=64')
    return vals


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fd:
        for buf in iter(lambda: fd.read(1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def require_lpips(device: str, net: str):
    try:
        import lpips  # official richzhang/PerceptualSimilarity distribution
        import torch
        import numpy as np
        from PIL import Image
    except (ImportError, RuntimeError, OSError) as exc:
        fail('Real LPIPS/PyTorch/Pillow not importable; install pinned requirements on '
             f'a compatible environment: {exc}')
    if device == 'cuda' and not torch.cuda.is_available():
        fail('CUDA requested but not available; use --device cpu instead')
    try:
        model = lpips.LPIPS(net=net, version='0.1', verbose=False)
        model = model.to(device).eval()
    except Exception as exc:
        fail(f'Official LPIPS pretrained weights not available or incompatible: {exc}')
    return model, torch, np, Image


def load_tensor(path, torch, np, Image, device, crop):
    try:
        with Image.open(path) as im:
            if im.format != 'PNG':
                fail(f'File is not a PNG: {path}')
            im.load()
            dimensions = im.size
            if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
                rgba = im.convert('RGBA')
                a0, a1 = rgba.getchannel('A').getextrema()
                if a0 != 255 or a1 != 255:
                    fail(f'Transparent PNG found: {path}. Composite the same background first')
            if crop:
                x, y, w, h = crop
                if x + w > im.width or y + h > im.height:
                    fail(f'Crop outside screenshot {path}: {dimensions}')
                im = im.crop((x, y, x + w, y + h))
            if min(im.size) < 64:
                fail(f'LPIPS screenshot requires >=64px each axis: {path}: {im.size}')
            arr = np.asarray(im.convert('RGB'), dtype=np.uint8).copy()
    except (OSError, SyntaxError) as exc:
        fail(f'Cannot decode PNG {path}: {exc}')
    # Official LPIPS expects RGB [N,3,H,W] scaled to [-1,1].
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    tensor = tensor.to(device=device, dtype=torch.float32).div_(127.5).sub_(1.0)
    return tensor, dimensions


def measure(model, torch, t0, t1):
    with torch.inference_mode():
        value = float(model(t0, t1).item())
    if not math.isfinite(value):
        fail('LPIPS returned non-finite distance')
    return value


def main(argv=None):
    ap = argparse.ArgumentParser(description='BLOCKWILD real LPIPS aligned-frame benchmark')
    sp = ap.add_subparsers(dest='command', required=True)
    d = sp.add_parser('doctor', help='Inspect optional dependencies; do not install them')
    d.add_argument('--json', action='store_true', help='Print machine-readable diagnostics')
    p = sp.add_parser('distance', help='Compute perceptual distance between A and B')
    p.add_argument('--a', type=Path, required=True)
    p.add_argument('--b', type=Path, required=True)
    add_shared(p)
    g = sp.add_parser('gain', help='Measure relative LPIPS distance reduction to a reference')
    g.add_argument('--reference', type=Path, required=True)
    g.add_argument('--before', type=Path, required=True)
    g.add_argument('--after', type=Path, required=True)
    add_shared(g)
    args = ap.parse_args(argv)

    if args.command == 'doctor':
        names = ('lpips', 'torch', 'torchvision', 'Pillow', 'numpy')
        versions = {}
        for name in names:
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
        result = {'required_runtime': 'official lpips 0.1.4 / PyTorch / torchvision / Pillow / numpy',
                  'installed_versions': versions,
                  'ready_for_lpips_import': bool(all(versions.values()))}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result['ready_for_lpips_import'] else 2

    inputs = ((args.a, args.b) if args.command == 'distance' else
              (args.reference, args.before, args.after))
    for inp in inputs:
        if not inp.exists():
            fail(f'Capture input not found: {inp}')
    pairs = paths_group(*inputs)
    crop = crop_tuple(args.crop)
    model, torch, np, Image = require_lpips(args.device, args.net)
    frames = []
    for name, paths in pairs:
        loaded = [load_tensor(p, torch, np, Image, args.device, crop) for p in paths]
        dimensions = [dim for _, dim in loaded]
        if len(set(dimensions)) != 1:
            fail(f'Mismatched viewport dimensions at {name}: {dimensions}')
        tensors = [v for v, _ in loaded]
        common = {'frame': name, 'size': list(dimensions[0]),
                  'sha256': {role: sha256(path) for role, path in zip(
                      ('a','b') if args.command=='distance' else ('reference','before','after'), paths)}}
        if args.command == 'distance':
            common['distance'] = measure(model, torch, tensors[0], tensors[1])
        else:
            common['before_distance'] = measure(model, torch, tensors[0], tensors[1])
            common['after_distance'] = measure(model, torch, tensors[0], tensors[2])
        frames.append(common)
    result = {
        'metric': 'LPIPS', 'lpips_model': args.net, 'lpips_version': '0.1',
        'package_version': importlib.metadata.version('lpips'),
        'device': args.device,
        'comparison_type': args.command,
        'capture_count': len(frames),
        'crop': list(crop) if crop else None,
        'meaning': ('LPIPS is a reference similarity distance, not an aesthetic quality percent.'
                    ' Same camera/pose/timestep/exposure must be supplied by the caller.'),
        'frames': frames,
    }
    if args.command == 'distance':
        result['mean_distance'] = statistics.fmean(f['distance'] for f in frames)
        result['quality_improvement_pct'] = None
    else:
        old = statistics.fmean(f['before_distance'] for f in frames)
        new = statistics.fmean(f['after_distance'] for f in frames)
        # This ratio is a relative change in LPIPS-to-reference distance only.
        gain = (100.0 * (old-new)/old) if old > 1e-8 else None
        result.update({'mean_before_distance':old,
                       'mean_after_distance':new,
                       'relative_reference_distance_reduction_pct':gain,
                       'quality_improvement_pct':None,
                       'reason_if_null':('Zero/near-zero baseline LPIPS: ratio undefined'
                                         if gain is None else None)})
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + '\n', encoding='utf-8')
    print(payload)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, PermissionError) as exc:
        print(f'BLOCKWILD LPIPS: {exc}', file=sys.stderr)
        sys.exit(2)
