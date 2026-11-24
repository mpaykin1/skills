#!/usr/bin/env python3
"""Official MobileSAM ViT-T on CPU -> image-space object labels (.npz).

Does not classify semantic categories. No synthetic segmentation fallback.
Independent upstream source/checkpoint downloaded by setup or first inference.
"""
from __future__ import annotations
import argparse
import sys
import urllib.request
from pathlib import Path


UPSTREAM_WEIGHTS = 'https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt'


def ensure_weights(repo: Path, custom: Path | None) -> Path:
    if custom is not None:
        path = custom.resolve()
        if not path.is_file() or path.stat().st_size < 1_000_000:
            raise RuntimeError('MobileSAM weight file missing or invalid: ' + str(path))
        return path
    path = repo / 'weights' / 'mobile_sam.pt'
    if path.is_file() and path.stat().st_size > 1_000_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.part')
    try:
        urllib.request.urlretrieve(UPSTREAM_WEIGHTS, str(tmp))
        if tmp.stat().st_size <= 1_000_000:
            raise RuntimeError('Downloaded MobileSAM checkpoint is empty / Git LFS pointer')
        tmp.replace(path)
        return path
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise RuntimeError('Official MobileSAM checkpoint not available. Download it from '
                           'https://github.com/ChaoningZhang/MobileSAM/tree/master/weights '
                           'and pass --segment-weights /path/mobile_sam.pt') from e


def compose_labels(masks, height, width, min_area_fraction=0.0012, max_objects=80):
    """Deterministic non-overlapping instance masks, not semantic class IDs.

    Larger masks are painted first; more localized masks overwrite them.
    Uncovered pixels remain zero. Reject nearly full-frame masks.
    """
    import numpy as np
    result = np.zeros((height, width), dtype=np.uint16)
    candidates = []
    min_area = max(48, round(height * width * min_area_fraction))
    for m in masks:
        mask = np.asarray(m['segmentation'], dtype=bool)
        area = int(mask.sum())
        if mask.shape != (height, width) or area < min_area or area > height * width * 0.88:
            continue
        if float(m.get('predicted_iou', 1)) < 0.70 or float(m.get('stability_score', 1)) < 0.80:
            continue
        candidates.append((area, float(m.get('predicted_iou', 1)), mask))
    # rank by area and quality; limit expensive overlap masks for CPU output.
    candidates.sort(key=lambda x: (-x[0], -x[1]))
    candidates = candidates[:max_objects]
    count = 0
    for _, _, mask in candidates:
        # Fully occluded masks are not registered as objects.
        if not np.any(result[mask] == 0) and np.count_nonzero(mask) < min_area*2:
            continue
        count += 1
        result[mask] = count
    return result, count


def main():
    ap = argparse.ArgumentParser(description='MobileSAM automatic object-instance segmentation on CPU')
    ap.add_argument('photo', type=Path)
    ap.add_argument('--output', '-o', type=Path, required=True)
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1] / 'vendor' / 'MobileSAM')
    ap.add_argument('--weights', type=Path)
    ap.add_argument('--points-per-side', type=int, default=10)
    ap.add_argument('--max-objects', type=int, default=80)
    ap.add_argument('--min-area-fraction', type=float, default=0.0012)
    args = ap.parse_args()
    if not args.photo.is_file(): ap.error('Input image missing')
    if not (args.repo / 'mobile_sam' / '__init__.py').is_file():
        ap.error('Official MobileSAM repository missing: run scripts/setup_cpu.sh or .ps1')
    if not 4 <= args.points_per_side <= 32: ap.error('--points-per-side must be in 4..32')
    if not 1 <= args.max_objects <= 200: ap.error('--max-objects must be in 1..200')
    if not 0 < args.min_area_fraction < 0.1: ap.error('invalid --min-area-fraction')

    import numpy as np
    from PIL import Image, ImageOps
    import torch
    sys.path.insert(0, str(args.repo.resolve()))
    from mobile_sam import SamAutomaticMaskGenerator, sam_model_registry
    weights = ensure_weights(args.repo.resolve(), args.weights)
    rgb = np.asarray(ImageOps.exif_transpose(Image.open(args.photo)).convert('RGB'), dtype=np.uint8)
    model = sam_model_registry['vit_t'](checkpoint=str(weights))
    model.to(device='cpu').eval()
    # On CPU, lower the prompt grid density and batch size vs upstream defaults.
    generator = SamAutomaticMaskGenerator(model, points_per_side=args.points_per_side,
                                         points_per_batch=8, pred_iou_thresh=0.72,
                                         stability_score_thresh=0.80,
                                         crop_n_layers=0, min_mask_region_area=0)
    with torch.inference_mode():
        masks = generator.generate(rgb)
    labels, count = compose_labels(masks, rgb.shape[0], rgb.shape[1],
                                    args.min_area_fraction, args.max_objects)
    if count == 0:
        raise RuntimeError('MobileSAM found no reliable object regions; use --segment-mode off')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, labels=labels)
    print(f'MobileSAM CPU: {count} object-region masks in {args.output} ({labels.shape[1]}x{labels.shape[0]})')


if __name__ == '__main__':
    main()
