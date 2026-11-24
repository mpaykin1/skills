#!/usr/bin/env python3
"""OpenCV 4 structural-line guard for MoGe/DA-V2/MobileSAM image-to-3D.

Genuine CPU image processing: blur + Canny + probabilistic Hough segments.
A UV-aligned confidence raster suppresses only DA-V2 *extra* displacement
near long image edges. Geometry/UV/texture come exclusively from MoGe.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np


def structural_confidence(image_bgr: np.ndarray, guard_pixels: int = 5,
                          max_side: int = 1024, min_length_fraction: float = 0.09,
                          max_lines: int = 250):
    """Return (float32 HxW confidence, int32 Nx4 segments) in image coordinates.

    Input may contain shadows/foliage. Use only sufficiently long segments
    to avoid freezing all depth refinement on fine texture. No semantic labels
    or vanishing-point claims are inferred from this operation.
    """
    import cv2
    image_bgr = np.asarray(image_bgr)
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3 or image_bgr.dtype != np.uint8:
        raise ValueError('OpenCV expects uint8 HxWx3 BGR image')
    if not (1 <= guard_pixels <= 40):
        raise ValueError('guard_pixels must be between 1 and 40')
    if not (128 <= max_side <= 4096):
        raise ValueError('max_side must be between 128 and 4096')
    if not (0.03 <= min_length_fraction <= 0.5):
        raise ValueError('min_length_fraction must be between .03 and .5')
    if not (1 <= max_lines <= 1000):
        raise ValueError('max_lines must be between 1 and 1000')
    h0, w0 = image_bgr.shape[:2]
    if min(h0, w0) < 16:
        raise ValueError('Photo is too small for reliable OpenCV structure detection')
    scale = min(1., max_side / max(h0, w0))
    if scale < 1:
        image_bgr = cv2.resize(image_bgr, (max(2, round(w0*scale)), max(2, round(h0*scale))),
                               interpolation=cv2.INTER_AREA)
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    smoothed = cv2.GaussianBlur(gray, (5, 5), 0)
    # Analyze gradient contrast instead of absolute brightness (night scenes).
    gx = cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smoothed, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    q = float(np.percentile(mag, 86))
    hi = float(np.clip(q, 40., 180.))
    edges = cv2.Canny(smoothed, hi * .43, hi, L2gradient=True)
    # Require a minimum physical line length in image space; filter short noise.
    min_length = max(20, int(min(h, w) * min_length_fraction))
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=max(15, int(min(h, w)*.035)),
                            minLineLength=min_length, maxLineGap=max(3, int(min(h, w)*.015)))
    result_lines = np.empty((0, 4), dtype=np.int32)
    if lines is not None:
        line_array = np.asarray(lines, dtype=np.int32).reshape(-1, 4)
        lengths = np.hypot(line_array[:, 2]-line_array[:, 0], line_array[:, 3]-line_array[:, 1])
        ranked = np.argsort(-lengths, kind='stable')
        result_lines = line_array[ranked[:max_lines]]
    if not len(result_lines):
        return np.ones((h,w), dtype=np.float32), result_lines
    contour_mask = np.zeros((h,w), dtype=np.uint8)
    thickness = max(1, int(round(min(h, w) / 450)))
    for x0, y0, x1, y1 in result_lines:
        cv2.line(contour_mask, (int(x0), int(y0)), (int(x1), int(y1)), 255, thickness,
                 lineType=cv2.LINE_8)
    # Guard radius is measured in the downsampled raster coordinate system.
    dist = cv2.distanceTransform((contour_mask == 0).astype(np.uint8), cv2.DIST_L2, 3)
    confidence = np.clip(dist / guard_pixels, 0, 1).astype(np.float32)
    return confidence, result_lines


def run(photo: Path, output: Path, guard_pixels=5, max_side=1024,
        min_length_fraction=.09, max_lines=250):
    import cv2
    # Pillow handles Unicode paths and EXIF camera orientation across platforms.
    from PIL import Image, ImageOps
    try:
        with Image.open(photo) as src:
            rgb = np.asarray(ImageOps.exif_transpose(src).convert('RGB'))
    except OSError as exc:
        raise ValueError(f'Cannot read photo for OpenCV analysis: {photo}') from exc
    image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    confidence, lines = structural_confidence(image, guard_pixels, max_side,
                                               min_length_fraction, max_lines)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, confidence=confidence.astype(np.float16),
                        lines=lines.astype(np.int32))
    print(f'OpenCV: {len(lines)} structural lines; guard raster {confidence.shape[1]}x{confidence.shape[0]}')
    return output


def load_structure(path: Path):
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != {'confidence','lines'}:
            raise ValueError('OpenCV .npz requires exactly confidence and lines arrays')
        confidence, lines = archive['confidence'].astype(np.float32), archive['lines']
    if (confidence.ndim != 2 or min(confidence.shape) < 2 or not np.isfinite(confidence).all()
        or np.any((confidence < 0) | (confidence > 1))):
        raise ValueError('OpenCV confidence must be a finite 2D map in [0,1]')
    if lines.ndim != 2 or lines.shape[1] != 4 or lines.dtype.kind not in 'iu':
        raise ValueError('OpenCV lines must be Nx4 integers')
    return confidence


def main():
    parser = argparse.ArgumentParser(description='Extract architectural line guards with CPU OpenCV')
    parser.add_argument('photo', type=Path)
    parser.add_argument('--output', '-o', required=True, type=Path)
    parser.add_argument('--guard-pixels', type=int, default=5)
    parser.add_argument('--max-side', type=int, default=1024)
    parser.add_argument('--min-length-fraction', type=float, default=.09)
    parser.add_argument('--max-lines', type=int, default=250)
    args = parser.parse_args()
    run(args.photo, args.output, args.guard_pixels, args.max_side,
        args.min_length_fraction, args.max_lines)


if __name__ == '__main__':
    main()
