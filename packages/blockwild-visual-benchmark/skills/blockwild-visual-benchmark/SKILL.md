---
name: blockwild-visual-benchmark
description: "Measure actual BLOCKWILD gameplay screenshot perceptual differences using the official BSD-2-Clause LPIPS model; reuse native/browser frame capture and assess relative closeness to an approved visual reference without inventing graphical improvement percentages."
---

# BLOCKWILD Visual Benchmark — LPIPS v0.1.0

## Purpose
When the owner asks to objectively measure how BLOCKWILD v9/v10/newer visually changed, measure *real screenshots* using the official [richzhang/PerceptualSimilarity](https://github.com/richzhang/PerceptualSimilarity) (LPIPS), not guesses or fabricated percentages. This skill adds a diagnostic adapter, **not** a new renderer or competing engine; do not alter the original game.

## Integrates with our author skills
- **BLOCKWILD Evolution**: choose comparison as the next step when visual claims lack proof; this tool supplies bounded metric signals and a source hash to Evolution, not permission for blind automatic artwork changes.
- **Godot + Unity → HTML / browser-parity-capture**: get synchronized source Unity/native Web, HTML v9 and HTML v10 screenshot frames (Playwright 1.65.1). Identical viewport, DPR, frame/time, region, weather RNG seed, camera, FOV, exposure, UI state and input.
- **Meta Game Fusion / Sprite Stacking Grunge / Voxel Game Creator / Blender Model Animation Enhancer**: compare the same approved object, angle and scene before/after; use target original when measuring fidelity. Never replace original graphics because a score alone improves.
- **Hero Animator**: assess stable full-body action sprites only for the same actor pose/animation frame; **LPIPS alone cannot measure animation smoothness**, FPS, correctness, jitter, gameplay, collisions or identity.
- **Skill Nexus**: consume only truthful frame-pair results; do not equate loss improvement with art quality or independent game validation.

## Underlying OSS
Official LPIPS package **lpips==0.1.4**, BSD-2-Clause; backbone AlexNet by default, official linear calibration v0.1. PyTorch, torchvision, numpy, Pillow installed in a separate reproducible Python environment with compatible versions. The original source is not copied into the skill. Pretrained models and upstream dependencies are optional build-time requirements, **not present in the offline game's HTML**. No silent model download and no fake scores if weights cannot be loaded. The LPIPS library may cause torchvision to download pretrained backbone weights on first use; install/cache those in a controlled networked environment beforehand.

## Run
From this skill root (`skills/blockwild-visual-benchmark`):

```bash
python scripts/benchmark.py doctor
# Paired screenshots: tells visual difference, NOT improvement %:
python scripts/benchmark.py distance --a path/to/v9_frames --b path/to/v10_frames --net alex
# Approved original / before / after with identical file names and geometry:
python scripts/benchmark.py gain --reference path/to/approved_source_frames --before path/to/v9_frames --after path/to/v10_frames --net alex
```

For a verified and approved local environment only: `python -m pip install -r requirements.txt` after selecting a PyTorch/torchvision pair appropriate to CPU/GPU (follow official PyTorch instructions). `python scripts/benchmark.py doctor` checks package versions; benchmark execution verifies actual imports and official pretrained model weights. Do not modify core environment automatically.

Images accepted: PNG files or identical recursive relative paths of PNGs in each directory; exact viewport dimensions enforced; auto-resizing is forbidden. `--crop x,y,width,height` applies the **identical** non-UI ROI to each frame. Fully transparent RGBA screenshots rejected. `--device cpu|cuda` defaults to CPU. `--out results.json` is optional; never place diagnostics in the source game's files unless explicitly requested.

## Interpretation
- `distance`: single pair or mean LPIPS distance. **Lower** = more visually similar. No valid artistic improvement percentage from this comparison.
- `gain`: `100 * (mean_before_distance − mean_after_distance) / mean_before_distance`; strictly **relative reduction in distance to an approved visual reference**, may be negative. With zero baseline, percentage is undefined (`null`). Neither 100% coverage of block IDs nor reduced LPIPS means “game graphics improved by X%.”
- A reference-free aesthetic preference, original Unity content fidelity, animation temporal quality, scene consistency, and perceptual preference are not calculable from LPIPS alone. The user may approve an A/B preference evaluation separately.
- Record model, version, source PNG hashes, viewport/crop, timestamps from original capture protocol (if available), frame count; avoid arbitrary mismatched screenshots.

## Safety / release gates
Original BLOCKWILD Windows ZIP, native gameplay, author's art, 95 material IDs, HTML v9/v10 remain immutable. No protected `meta6` writes, no unauthorized distribution of Unity assets or copyrighted weights. No public game URL or visual PASS unless browser frames and runtime were genuinely verified. Follow animated-world-guard, source identity and licensing rules. Source license: see `references/LPIPS_UPSTREAM.md`.
