# OpenCV 4 CPU integration

- Official upstream: https://github.com/opencv/opencv
- Python wheel: https://pypi.org/project/opencv-python-headless/
- License: Apache-2.0 (OpenCV >=4.5); no upstream source or binaries bundled into this plugin.
- `scripts/opencv_structure.py`: grayscale + Gaussian blur + Canny + probabilistic HoughLinesP. Keeps long structural 2D line segments, calculates distanceTransform confidence within a configurable safety radius.
- The `.npz` has exactly `confidence` (float16 HxW in 0..1), `lines` (int32 Nx4 image endpoints); requires original-photo alignment.
- `build_location.py` UV-samples this raster with the same bottom-left UV / top-left photo flip as Depth Anything. The `min(MobileSAM_boundary_confidence, OpenCV_line_confidence)` is multiplied onto **only extra DA-V2 residual depth correction**; MoGe geometry, original texture and UV topology remain unchanged.
- Default OpenCV auto detection is deterministic and CPU-only; when no qualified lines exist the confidence is all ones (no change). No fake camera calibration, no 3D polygon simplification, no classification of features.
- Inference uses photo; cached `.npz` can be used with --from-glb when source photo isn't available. Use `--opencv-mode off` to explicitly disable it.
- Upstream APIs: https://docs.opencv.org/4.x/d9/db0/tutorial_hough_lines.html .
