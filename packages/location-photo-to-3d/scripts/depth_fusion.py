#!/usr/bin/env python3
"""Conservative single-view fusion of MoGe-2 GLB z and DA-V2 relative depth.

Sampling uses UV correspondence to the original input. DA depth never overrides
MoGe metric scale or camera intrinsics. Rays remain fixed; only z changes.
"""
from __future__ import annotations
import numpy as np


def sample_bilinear(image, uv):
    """Depth map top-left origin, OpenGL UV bottom-left origin."""
    if image.ndim != 2:
        raise ValueError('Depth Anything map must be HxW')
    h, w = image.shape
    if h < 2 or w < 2:
        raise ValueError('Depth Anything map too small')
    u = np.asarray(uv, dtype=np.float64)
    x = np.clip(u[:, 0], 0, 1) * (w-1)
    y = (1-np.clip(u[:, 1], 0, 1)) * (h-1)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0+1, w-1)
    y1 = np.minimum(y0+1, h-1)
    fx = x-x0
    fy = y-y0
    return ((1-fx)*(1-fy)*image[y0, x0] + fx*(1-fy)*image[y0, x1]
            + (1-fx)*fy*image[y1, x0] + fx*fy*image[y1, x1])


def robust_line_fit(x, y):
    """Fit log metric-depth from relative DA map, 4 robust reweightings."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xm, xs = np.median(x), np.percentile(x, 75)-np.percentile(x, 25)
    if xs < 1e-7:
        return None
    t = (x-xm)/xs
    A = np.stack([t, np.ones_like(t)], axis=1)
    # Avoid huge solve when many vertices: deterministic equispaced subset.
    if len(t) > 50000:
        inds = np.linspace(0, len(t)-1, 50000, dtype=np.int64)
        A, y = A[inds], y[inds]
    weights = np.ones(len(y), dtype=np.float64)
    coef = np.zeros(2)
    for _ in range(5):
        aw = A*weights[:, None]
        coef = np.linalg.lstsq(aw, y*weights, rcond=None)[0]
        residual = y-A@coef
        scale = 1.4826*np.median(np.abs(residual-np.median(residual)))+1e-7
        weights = np.clip(1.5*scale/(np.abs(residual)+1e-7), 0, 1)
    return coef, xm, xs


def refine_vertices(vertices, uvs, depth_map, strength=0.35, vertex_confidence=None):
    """Return camera-ray corrected vertices and effective fusion flag.

    Strategy: robust alignment of DA relative values to MoGe log-depth; local
    residual bounded to ±12% scale. Skip if directions fail to correlate. No
    invented backside geometry or changes to source texture or triangle topology.
    """
    vertices = np.asarray(vertices, dtype=np.float32)
    uvs = np.asarray(uvs, dtype=np.float32)
    if strength <= 0 or len(vertices) < 25:
        return vertices, False
    if not 0 <= strength <= 1:
        raise ValueError('strength must be in [0,1]')
    if np.asarray(depth_map).dtype.kind not in 'fi':
        raise ValueError('Depth map must be floating point')
    # OpenGL convention exported by MoGe, camera looking down -Z.
    z = -vertices[:, 2].astype(np.float64)
    rel = sample_bilinear(np.asarray(depth_map, dtype=np.float32), uvs)
    use = np.isfinite(z)&(z>1e-5)&np.isfinite(rel)&(uvs[:, 0]>=0)&(uvs[:, 0]<=1)&(uvs[:, 1]>=0)&(uvs[:, 1]<=1)
    if use.sum() < 25:
        return vertices, False
    zlog = np.log(np.maximum(z, 1e-6))
    qlo, qhi = np.percentile(rel[use], [2, 98])
    zlo, zhi = np.percentile(zlog[use], [2, 98])
    fitmask = use & (rel>=qlo)&(rel<=qhi)&(zlog>=zlo)&(zlog<=zhi)
    if fitmask.sum() < 25:
        return vertices, False
    x, y = rel[fitmask], zlog[fitmask]
    rho = np.corrcoef(x, y)[0, 1] if np.std(x)>1e-7 and np.std(y)>1e-7 else 0
    if not np.isfinite(rho) or abs(rho)<0.18:
        return vertices, False
    fit = robust_line_fit(x, y)
    if fit is None:
        return vertices, False
    coef, xm, xs = fit
    expected = coef[0]*(rel-xm)/xs + coef[1]
    residual = expected-zlog
    center = np.median(residual[fitmask])
    residual = np.nan_to_num(residual-center, nan=0, posinf=0, neginf=0)
    # Absolute change cap: ±12% from original metric depth, scaled by strength.
    residual = np.clip(residual, -np.log(1.12), np.log(1.12))
    if vertex_confidence is not None:
        confidence = np.asarray(vertex_confidence, dtype=np.float64)
        if confidence.shape != z.shape or not np.isfinite(confidence).all():
            raise ValueError('MobileSAM confidence must be finite and match vertex count')
        confidence = np.clip(confidence, 0.0, 1.0)
    else:
        confidence = 1.0
    new_z = z*np.exp(residual*strength*confidence)
    ratio = np.ones_like(z)
    ratio[use] = new_z[use]/z[use]
    corrected = (vertices.astype(np.float64)*ratio[:, None]).astype(np.float32)
    if not np.isfinite(corrected).all():
        raise RuntimeError('Depth fusion produced invalid geometry')
    return corrected, True
