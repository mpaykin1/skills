#!/usr/bin/env python3
"""MobileSAM object-instance boundaries -> confidence for MoGe/DA-V2 fusion.

Important: MobileSAM segmentation is NOT semantic labeling and NOT new geometry.
The original mesh and triangle topology remain unchanged; near seams the
relative depth residual receives less weight, limiting rubber-sheet artifacts.
"""
from __future__ import annotations
import numpy as np


def sample_nearest(image, uvs):
    """OpenGL UV bottom-left, image top-left. Samples exact nearest pixel."""
    uv = np.asarray(uvs, dtype=np.float64)
    if uv.ndim != 2 or uv.shape[1] != 2 or not np.isfinite(uv).all():
        raise ValueError('UVs must be finite Nx2')
    h, w = image.shape
    if h < 2 or w < 2: raise ValueError('Segmentation map is too small')
    x = np.rint(np.clip(uv[:, 0], 0, 1) * (w-1)).astype(np.int64)
    y = np.rint((1-np.clip(uv[:, 1], 0, 1)) * (h-1)).astype(np.int64)
    return image[y, x]


def boundary_confidence(labels, uvs, safety_pixels=4):
    """Weight 0..1; 0 at object seams, 1 in smooth interior of regions.

    Confidence applies only to displacement contributed by DA-V2, never to
    MoGe's original vertices. Where no MobileSAM region exists, keep MoGe.
    """
    import cv2
    labels = np.asarray(labels)
    if labels.ndim != 2 or labels.dtype.kind not in 'ui':
        raise ValueError('MobileSAM label map must be 2D unsigned integers')
    if not 1 <= safety_pixels <= 40: raise ValueError('safety_pixels out of range')
    h, w = labels.shape
    border = np.zeros((h, w), dtype=bool)
    different_v = labels[1:] != labels[:-1]
    different_h = labels[:, 1:] != labels[:, :-1]
    border[1:] |= different_v
    border[:-1] |= different_v
    border[:, 1:] |= different_h
    border[:, :-1] |= different_h
    if not border.any():
        return np.zeros(len(uvs), dtype=np.float32) if np.count_nonzero(labels) == 0 else np.ones(len(uvs), dtype=np.float32)
    # Nonzero away from border; distanceTransform returns 0 on border pixels.
    distance = cv2.distanceTransform(np.ascontiguousarray(~border, dtype=np.uint8), cv2.DIST_L2, 3)
    conf = np.clip(sample_nearest(distance, uvs) / safety_pixels, 0, 1).astype(np.float32)
    conf[sample_nearest(labels, uvs) == 0] = 0
    return conf
