---
name: location
version: 0.4.0
description: "ЛОКАЦИЯ: 3D-локация по фото через MoGe-2 ViT-S, Depth Anything V2 Small, MobileSAM ViT-T и OpenCV 4 (CPU), с сохранением фототекстуры и экспортом автономного HTML."
---

# ЛОКАЦИЯ — real photo to offline 3D HTML

## Trigger

When user provides environment photo and asks for close-reference 3D world, an autonomous HTML location, reconstruction, or «сделай локацию», execute the installed pipeline and provide the finished file if available. Do not merely describe steps when file creation is possible.

## Required four-way synergy (CPU inference)

1. **MoGe-2 ViT-S**: official `Ruicheng/moge-2-vits-normal` with `--device cpu`, `--version v2`, `--glb --maps`: visible textured geometry, camera, UV. No synthetic substitutes.
2. **Depth Anything V2 Small**: official ViT-S from `DepthAnything/Depth-Anything-V2` on CPU provides **relative** depth. `depth_fusion.py` aligns it robustly to MoGe log-depth and limits deformation to at most 12% at full strength while preserving camera rays.
3. **MobileSAM ViT-T**: official `ChaoningZhang/MobileSAM`, `SamAutomaticMaskGenerator` using `vit_t` on CPU; `mobile_sam_cpu.py` creates object-instance masks in `.npz`. These are **not semantic categories**. `segmentation_fusion.py` derives per-vertex confidence from object boundaries. `depth_fusion.py` applies confidence *only to its extra depth displacement*, so near mask seams the original MoGe shape remains protected. A true three-project integrated path, not independent feature output.
4. **OpenCV 4 structural guard**: `opencv_structure.py` applies CPU grayscale/Gaussian/Canny and probabilistic HoughLinesP to the same original photo, selecting long connected structural edges. The confidence raster is UV-sampled in `build_location.py`, combined by per-vertex minimum with MobileSAM boundary confidence, and supplied to `depth_fusion.refine_vertices`. This guard only attenuates *DA-V2 extra displacement*, not MoGe geometry, UV, triangle indices or original photography. Helps preserve long rooflines, façade edges, horizons and other prominent outlines where the photo clearly contains them; it is NOT a 3D line reconstruction or certainty about hidden surfaces. If no qualifying lines, the confidence raster is all ones and no OpenCV-guided change is claimed.
5. **Viewer**: `build_location.py` bakes actual MoGe positions, textures, and optional conservative fused positions into a single self-contained WebGL2 HTML. Desktop and mobile controls, no viewing CDN or external calls.

## Default process

First installation (internet): Linux/macOS `bash scripts/setup_cpu.sh`; Windows PowerShell `powershell -ExecutionPolicy Bypass -File scripts/setup_cpu.ps1`. Model checkpoints downloaded separately at first inference; don't falsely say they are bundled.

Then:

```sh
.venv/bin/python scripts/build_location.py photo.jpg -o /mnt/data/location.html
```

Windows Python: `.venv\Scripts\python.exe`.

CPU speed / precision: `--opencv-max-side 768` can reduce OpenCV workload; `--opencv-guard-pixels 5` sets protection width. `--opencv-min-line-fraction .09` ignores small noisy edges.  `--segment-grid 6` faster but fewer masks; default 10. `--resize 448 --resolution 1 --depth-input-size 392` lighter. Boundary protection radius defaults to `--seam-pixels 4`.

Optional cache: `--from-glb genuine_moge.glb --depth-map original_da_v2.npy --segment-map original_mobile_sam.npz` reuses actual model outputs; segmentation npz has exactly `labels`, unsigned HxW. Can pass `--depth-weights` and `--segment-weights` to reuse official checkpoint paths. `--depth-repo` and `--segment-repo` use existing upstream clones.

Explicit fallback when optional stages unavailable: `--opencv-mode off` skips only OpenCV. `--segment-mode off` skips only MobileSAM. For MoGe+DA-V2 use both `--segment-mode off --opencv-mode off`; for MoGe-only use `--segment-mode off --opencv-mode off --depth-mode off`. **Never** claim MobileSAM or DA-V2 ran in an off-mode build. If GLB only and no photo/map, choose all three off switches explicitly.

## HARD RULES

- Maintain exact photo texture, UVs, camera, triangle indices, source color / architecture, and close-reference geometry. Do not substitute abstract shapes or fake 3D just to produce a file.
- The 3 models plus OpenCV image processing operate on CPU; the browser uses WebGL2 hardware acceleration. One-source-photo cannot recover hidden geometry faithfully.
- OpenCV is image-line analysis, not semantic recognition, new geometry, or automatic perspective calibration. It cannot identify an object category. Do not infer hidden geometry from detected lines.
- MobileSAM is object/instance masking not semantic segmentation. It does not identify what a mask represents. Never say it automatically detected buildings versus trees.
- Prevent cross-object «rubber-sheet» distortions by fading *only Depth Anything corrections* near MobileSAM mask edges and OpenCV long structural lines. Do not remove original triangles based solely on uncertain instance masks.
- Validate geometry finite, segmentation image orientation consistent with UV, no missing materials and offline viewer with no CDN.
- Pin the OpenCV 4 headless binding `>=4.10,<5` and use CPU only. `opencv_structure.py` has no new learned weights.
- Source repository/weights are independent and NOT included; preserve upstream license references. Small Depth Anything ViT-S is Apache-2.0 (do not silently substitute models with other licenses).
- If source inference cannot be run, accurately distinguish integrated code from real executed inference; no ungrounded graphic fidelity metrics.
- User's outcome is the HTML itself, not reports. Keep outputs minimal, link only files that exist.

Sources: `reference/MOGE.md`, `reference/DEPTH_ANYTHING_V2.md`, `reference/MOBILESAM.md`, `reference/OPENCV.md`.
