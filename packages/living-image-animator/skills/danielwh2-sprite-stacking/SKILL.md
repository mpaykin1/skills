---
name: danielwh2-sprite-stacking
description: Direct real-source integration of the open-source MIT danielwh2/sprite-stacking four-view carving CLI with Living Image Animator's original-authored stack.json, Three.js 360° volume previews, optional PixiJS/Matter/YUKA gameplay and existing animation gates. Runs the authentic upstream, not an imitating reimplementation.
---

# danielwh2/sprite-stacking × Living Image Animator v0.38

**Original upstream:** https://github.com/danielwh2/sprite-stacking (MIT; Daniel White). This skill is bundled into the **same user-owned Living Image Animator plugin**. It supplies real `views_to_slices.py` 4-view carving, source render/check preview, original standalone interactive viewer, PNG slices and conversion to the pre-existing Living Image Animator `stack.json` format. **The original program is fetched once and Git blob SHA-pinned before execution. It is not silently replaced by another algorithm.** If source cannot be obtained and is not already cached, declare the missing dependency.

## Actual source-bound entrypoints

- `../living-image-animator/scripts/danielwh2_vendor.py`: installs/validates original `views_to_slices.py`, `viewer.html`, `SKILL.md`, `LICENSE`; compares each file against the reviewed official Git blob SHA. No unchecked `main`, no custom source pretending to be upstream.
- `../living-image-animator/scripts/danielwh2_delivery.py`: executes **that actual official program** with transparent/unquantized source settings, checks the produced original horizontal PNG slice strip, extracts independent bottom-up transparent PNG layers and emits `stack.json`, original viewer HTML, original check preview, source PNG, MIT license, manifest and ZIP.
- `../living-image-animator/scripts/sprite_stack_asset_preview.py`: optionally transforms the SAME exported `stack.json` into a real offline Three.js/WebGL2 `Data3DTexture` GLSL 360° volume viewer with a genuine locally available `three.module.js`. This viewer may be run separately if Three.js is unavailable; never call a fake engine installed.
- Existing `sprite_stacking_delivery.py`, `sprite_stacking_glb.py`, Godot/Blender, PixiJS/Matter/YUKA and author-supplied animated stacks can consume the resulting geometry **only after their own scene registration, approved original actor frame gates and runtime dependencies pass**. A single generic four-view reconstruction is NOT a complete character action/8-direction pack.

**One call from plugin root** (downloads official upstream only when necessary and network is available):

```bash
python skills/living-image-animator/scripts/danielwh2_delivery.py \
  my_authored_four_views.png --out ./stack-output --slices 36 --install-upstream
```

**Completely offline after a genuine source checkout is present:**

```bash
python skills/living-image-animator/scripts/danielwh2_delivery.py \
  my_authored_four_views.png --out ./stack-output \
  --upstream-root /path/to/authentic/sprite-stacking --slices 36 \
  --three-js /path/to/real/three.module.js
```

The actual external repo checkout must retain the original folder structure `skills/sprite-stacking/scripts/{views_to_slices.py,viewer.html}`, `skills/sprite-stacking/SKILL.md` and `LICENSE`, and must pass SHA inspection. This prevents unrelated or changed code from masquerading as the pinned upstream. When an updated upstream release changes SHA, audit before changing the pin.

## Rendering and identity

- Prefer a genuine authored 3D mesh sliced by the existing Sprite Stacking Grunge Horror skill or the user's original `stack.json` for **accurate** multi-view geometry and grunge texture. The external four-view visual-hull carve is only a reconstruction: it cannot recover cavities hidden from all orthographic views, and does not promise source accuracy from one picture.
- 90% of declared eligible environmental objects should use *real* stacks when source images exist; never inflate the eligible inventory. Architecture, objects, wheels, doors and machinery are preferred; car/art color must not change silently and no repeating voxel patterns.
- Original full-body actors (human, animal, NPC) NEVER get a substitute character from the four-view carver. Each animated action uses the same complete source-authored independently checked poses and explicit matching pose stack, or it stays in the original flat-cel animation. No mesh warp, cut-out deformation or optical-flow character motion.
- Open-source Python Pillow and NumPy are required, as required by the official tool. The optional true-volume preview requires a verified Three.js runtime. The generated original upstream HTML is self-contained after the genuine tool runs; no CDN.

**Release outputs:** `original_sprite_stack_viewer.html`, `slices_strip.png`, `original_four_view_preview.png`, `original_four_views.png`, `stack.json`, `layers/*.png`, `LICENSE.danielwh2.txt`, optional `threejs_360_volume.html`, and `stack-output_sprite_stacking.zip`. No source PNG strips or original artist frames are overwritten. No unrequested reports, tests or evidence.
