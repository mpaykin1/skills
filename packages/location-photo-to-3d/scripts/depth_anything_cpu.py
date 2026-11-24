#!/usr/bin/env python3
"""Official Depth Anything V2 Small ViT-S inference on CPU, outputs raw relative-depth .npy.

Repo code and checkpoint are obtained independently, under Apache-2.0; this
bridge does not vendor or silently replace either upstream model.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description='Depth Anything V2 Small CPU -> float32 depth map')
    p.add_argument('image', type=Path)
    p.add_argument('--output', '-o', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1] / 'vendor' / 'Depth-Anything-V2')
    p.add_argument('--weights', type=Path, help='Optional previously downloaded official ViT-S weights')
    p.add_argument('--input-size', type=int, default=518)
    args = p.parse_args()
    if not args.image.is_file():
        p.error(f'Image does not exist: {args.image}')
    if not (args.repo / 'depth_anything_v2' / 'dpt.py').is_file():
        p.error('Upstream Depth Anything V2 is missing. Run setup_cpu.sh or setup_cpu.ps1 first.')
    if args.input_size < 252:
        p.error('--input-size must be >=252')
    import cv2
    import numpy as np
    import torch
    sys.path.insert(0, str(args.repo.resolve()))
    from depth_anything_v2.dpt import DepthAnythingV2
    model = DepthAnythingV2(encoder='vits', features=64,
                           out_channels=[48, 96, 192, 384])
    if args.weights is not None:
        weights = args.weights.resolve()
        if not weights.is_file():
            p.error(f'Weights missing: {weights}')
    else:
        from huggingface_hub import hf_hub_download
        weights = Path(hf_hub_download(repo_id='depth-anything/Depth-Anything-V2-Small',
                                       filename='depth_anything_v2_vits.pth'))
    state_dict = torch.load(str(weights), map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model = model.to(torch.device('cpu')).eval()
    raw = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if raw is None:
        raise RuntimeError('Cannot decode input image')
    # No torch.autocast / CUDA / mps: full precision only on CPU.
    with torch.inference_mode():
        prediction = model.infer_image(raw, input_size=args.input_size)
    prediction = np.asarray(prediction, dtype=np.float32)
    if prediction.shape != raw.shape[:2] or not np.isfinite(prediction).all():
        raise RuntimeError('Depth Anything V2 returned invalid depth map')
    if np.ptp(prediction) < 1e-6:
        raise RuntimeError('Depth Anything V2 returned near-constant map')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(args.output), prediction, allow_pickle=False)
    print('Depth Anything V2 Small CPU map:', args.output, prediction.shape)


if __name__ == '__main__':
    main()
