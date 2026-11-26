---
name: visual-parity-guard
description: >
  Visual fidelity gate for approved original Godot/Unity/GLB screenshots via Mapbox Pixelmatch 8.0.0; prevents optimized textures, lighting or GLB scenes from replacing originals when aligned real-browser frames diverge. Complements Khronos glTF Validator, xatlas/Blender, OIDN, OpenImageIO, KTX2, glTF-Transform and native WebGL exports.
---

# Original Visual Parity Gate — Pixelmatch 8.0.0

## Role / interoperability

**Original playable Godot/Unity WebGL remains authoritative.** Image compare is a DIFFERENT safeguard than Khronos glTF Validator: glTF Validator checks metadata/schema/identities; Mapbox Pixelmatch detects visible changed pixels in real screenshots. Neither alone proves an exact remake, restored gameplay, visual improvement or browser compatibility. No renderer or engine substitution.

1. Obtain the original renderer screenshot and candidate WebGL/Three.js/PixiJS screenshot using **the same viewport, camera, FOV, exposure, colorspace, scene, and animation frame/time**. For «ЛЕЕР» the dynamic blizzard/fog and changing lighting must be frozen or captured deterministically. If this is not possible, report that parity cannot be measured; do not invent percentages.
2. Invoke `scripts/visual_parity.py --baseline /reference/original.png --candidate /derivative/optimized.png` (or matched directories with identical filenames for multi-frame captures).
3. The wrapper installs pinned Mapbox `pixelmatch@8.0.0` (ISC) plus `pngjs@7.0.0` (MIT) into an isolated user cache, only when permitted; `--no-install` fails closed without local deps. Runtime offline HTML contains neither dependency.
4. Default pixel perceptual tolerance `--threshold 0.10`; default maximal fraction of changed pixels `--max-ratio 0.03`. **These are configurable guardrails, not "97% visual fidelity".** Anti-aliasing variations are ignored unless `--include-aa` is requested. One failed frame blocks promotion. Any different resolution/name/count or absent image blocks evaluation. Optional `--diff-dir` writes diff PNGs outside the source folder only when explicitly requested.
5. For 3D: `--original-glb ORIGINAL.glb --optimized-glb OPTIMIZED.glb` adds existing Khronos glTF Validator's schema and identity check (Khronos code remains the sole validator; no duplicate parser). `--html-out candidate.html` builds existing offline Three.js **visual-only** HTML *only after* Pixelmatch and Khronos checks pass; native Godot/Unity build remains the playable game.
6. For 2D: compare approved original and candidate frames from `pixi-original-sprites`/`hero-animator`; never deform sprites or generate fake frames. For static scene AO: xatlas → Blender → OIDN → OpenImageIO → oxipng/KTX2 candidates; compare their **actual rendered** output, not just pixels of raw texture atlases.

## Commands

```bash
python skills/visual-parity-guard/scripts/visual_parity.py --baseline captures/original --candidate captures/optimized --max-ratio 0.03 --no-install
python skills/visual-parity-guard/scripts/visual_parity.py --baseline captures/original.png --candidate captures/optimized.png --original-glb original.glb --optimized-glb optimized.glb --html-out verified-visual.html
```

## Limits

The tool compares only aligned PNG raster frames; it cannot independently capture the original 3D game or restore missing 3D assets or logic. Weather, motion blur, procedural grain, particles and variable exposure can give false positives, so deterministic captures and human inspection remain essential. A low pixel difference percentage does not measure the total percentage of the original game's content retained; it only measures differences in supplied frames. Never auto-replace source files, material bindings, game logic or original shaders based only on this threshold. Do not produce reports or image diff artifacts unless requested.

Source: https://github.com/mapbox/pixelmatch (ISC). PNG decoding: https://github.com/pngjs/pngjs (MIT).
