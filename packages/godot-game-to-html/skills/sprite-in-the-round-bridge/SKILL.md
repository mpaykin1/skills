---
name: sprite-in-the-round-bridge
description: >
  Use official MIT SoAp9035/sprite-in-the-round to export real sprite-stacking volumes to GLB, OBJ, turntable, directional sprites, VOX, and its native HTML. Interoperates with danielwh2 four-view carving, existing META GAMES Grunge stack.json, static Unity/Godot-derived GLBs, Three.js WebGL2 volume raymarch and original game WebGL. Pinned upstream scripts run without CDN.
---

# META GAMES — sprite-in-the-round integration v1.20

**No replacement of previous modules:** This is a companion module inside the existing `godot-game-to-html` plugin. Continue to use the original native Godot/Unity WebGL game for actual gameplay. Source textures/GLBs/PNGs and engine scripts remain unchanged. Visual-hull reconstruction from insufficient views is an approximation, not restoration of unknown surfaces.

## Exact flow and cooperation

- **2–5 source orthographic views** (`top.png` + `side.png`, optionally `front.png`, `back.png`, `side2.png`) → original upstream `voxlib.stack_views()` → official bottom-first sprite slice sheet. Keep source colors (no automatic posterization, recoloring or stylization). The volume is only an estimate where sides are missing.
- **4 views on a single sheet** → previously integrated `danielwh2/sprite-stacking` pinned carver → approved Grunge `stack.json`. No duplicate carving implementation.
- **Original static Unity/Godot GLB** → existing `stack_from_glb.py` (original vertex colors/UV, rejecting animated/skinned inputs) → Grunge RGBA slices; never extract a fake static hero pose.
- **Approved Grunge `stack.json`** → faithful bottom-first native horizontal PNG strip → **official upstream `scripts/stack.py`** → GLB/OBJ + palette, 16-direction atlas, preview, native self-contained 2D viewer, optional turntable GIF/VOX.
- **Native `sprite-in-the-round` slice PNG** → separate original RGBA PNG layers and `stack.json` → the existing META GAMES Three.js WebGL2 real-volume renderer (yaw/pitch/360°). Multiple authored animation rows become *complete* individual pose stacks, consistent pivot and spacing; no cut-out distortion, no AI-generated frame interpolation.
- **Original web export** remains the gameplay route; glTF Validator, Playwright/Pixelmatch and KTX2/Basis only process approved derivatives with their own limitations.

The upstream implementation is real, obtained from **pinned Git commit `1d842b4d6d4e7f26b13236dedaf5841ecbfec267`** of https://github.com/SoAp9035/sprite-in-the-round (MIT). Installer gets it on first actual run; it is kept in a separate user cache with revision checking. This plugin ZIP ships only integration source and its own notices, *not* fake copies of upstream code or a generated game. Installation needs Git and network once, or an official local clone via `--upstream-root`. Runtime after HTML build needs no network. Build-time requirements: Python, Pillow, NumPy; Three.js/esbuild also requires Node.js/npm once.

## Commands from plugin root

```bash
# Input: one real author-designed RGBA stack.json (or folder containing stack.json).
python skills/godot-game-to-html/scripts/sprite_in_the_round.py art/stack.json --out /output/round-asset --gif --vox

# Input: 2–5 aligned individual PNG views in folder.
python skills/godot-game-to-html/scripts/sprite_in_the_round.py /views/ --out /output/from-views --gif

# Input: 4 orthographic views in one sheet; reuse danielwh2 carver.
python skills/godot-game-to-html/scripts/sprite_in_the_round.py fourviews.png --out /output/from-four --four-views --slices 64

# Input: an original static GLB, via previously installed GLB→stack source bridge.
python skills/godot-game-to-html/scripts/sprite_in_the_round.py original.glb --out /output/from-glb --gif

# Existing upstream horizontal strip without metadata: user states exact count.
python skills/godot-game-to-html/scripts/sprite_in_the_round.py slices.png --count 36 --out /output/from-strip
```

Outputs in the destination: `exports/sprite_stack.glb`, `.obj`, `.mtl`, `_palette.png`, `_dirs16.png`, `_preview.png`, `_viewer.html` and optional GIF/.vox, plus `sprite-stacking.html` from our real WebGL2 volume shader, and either reused author `stack.json` or generated `stacks/stack.json`. For multiple frames, `.glb` and `.obj` are **not** promised; upstream makes animated directional outputs and our full-pose HTML.

All frame counts and layer dimensions must be bounded. Our wrapper refuses to rebuild a model from inconsistent layer sizes, an empty volume, output inside original source data, or **anisotropic voxel pitch** that upstream's uniform-scale GLB writer would distort. The original Three.js volume viewer continues to support authored anisotropic stacks separately. `--no-html` exports only art assets; `--no-install-upstream` and `--no-install-js` enforce offline build dependencies.

See `references/INTEROP.md`. Licensing notice: `references/UPSTREAM_LICENSE.txt`.
