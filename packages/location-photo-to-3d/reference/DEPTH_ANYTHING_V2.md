# Depth Anything V2 Small (ViT-S) CPU bridge

Upstream: https://github.com/DepthAnything/Depth-Anything-V2
Official checkpoint: https://huggingface.co/depth-anything/Depth-Anything-V2-Small
License: upstream source Apache-2.0 and Small checkpoint Apache-2.0. Base/Large/Giant models CC-BY-NC-4.0; DO NOT use them by default.

Execution on CPU via `scripts/depth_anything_cpu.py` uses official `DepthAnythingV2(encoder='vits', features=64, out_channels=[48,96,192,384])`, official float32 `infer_image`, and cached checkpoint. It produces raw relative depth .npy (no misleading pseudo-metric scaling). No upstream code or weights shipped in the plugin ZIP; setup clones on first installation; weight downloaded once and cached by Hugging Face.

MoGe-2 GLB is authoritative: metric/camera framing, texture UVs, mesh topology, FOV and original photo stay unchanged. The `depth_fusion.py` bridge aligns relative prediction against log metric camera-depth using the MoGe GLB vertices and UV locations (OpenGL V points upward). After robust outlier rejection, it nudges vertex depths along the camera rays, caps depth correction at ±12% before strength scaling and keeps source colors. If correlation is too low, preserve the MoGe mesh and do not claim a successful refinement. UV image must represent the exact same photographed view; no independent crop/rotate.

When CPU resources are constrained: lower MoGe `--resize 448 --resolution 1`, Depth Anything `--depth-input-size 392`. If model or internet unavailable after first installation: `--depth-mode off` recovers MoGe-only workflow. Given already predicted raw map: `--depth-map depth.npy` avoids model inference without falsifying prediction.

### Examples

```bash
python scripts/build_location.py photo.jpg -o location.html
python scripts/build_location.py photo.jpg -o location.html --resize 448 --resolution 1 --depth-input-size 392
python scripts/build_location.py photo.jpg -o location.html --depth-mode off
python scripts/build_location.py --from-glb output/mesh.glb --depth-map output/depth_anything_v2.npy -o location.html
```

NOTE: the source photo is one viewpoint. This cannot recover hidden/occluded geometry. The correction is heuristic, not a proven universal quality improvement.
