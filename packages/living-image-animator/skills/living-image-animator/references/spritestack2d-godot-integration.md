# Genuine SpriteStack2D (Godot 4) × Living Image Animator

**Upstream:** https://github.com/VitSoonYoung/SpriteStack2D (MIT, ©2026 VitSoonYoung). Version is pinned to original Git commit `65f6d8dee65575ef3ee0f164698a2a1ecf93872b`, and the three official addon text files are verified by their genuine Git blob SHA-1 values. No fabricated SpriteStack2D implementation is provided. Original addon binary/source is downloaded **at build time** by `spritestack2d_vendor.py`, or passed as an authentic checkout via `--addon-root`; the source is then bundled in the export ZIP with its original license. Build requires network for the first fetch, but the resulting Godot project needs no network.

## Why this open source fits the existing engines

- **SpriteStack2D**: native Godot 4 node with built-in 4-view image-to-visual-hull carving, perspective rotator `y_rotations`, editor integration, shared source/angle cache, optional ground shadow and editable source art. Do not confuse with rendering literal existing Z-section PNG strips: SpriteStack2D accepts a **2 × 2 sheet containing TOP, FRONT, SIDE, BACK orthographic faces**. The TOP and SIDE views must point LEFT; Godot's original script internally rotates TOP 90° CCW when interpreting the sheet. Actual carving is a *visual hull*, so hidden cavities can be filled.
- **Original Three.js/GLSL slice volume**: unchanged and authoritative for original XY/Z stack rendering and interior details. The Godot adapter can project the same original painted RGBA Z-sections into four orthographic views without inventing pixel colors, but the subsequent 4-view visual hull is **not guaranteed to recover identical hidden geometry**. For maximal surface fidelity the original artist can supply a real original 2x2 face sheet via `sprite_stack2d.face_sheets`.
- **Godot native original actor/physics/path**: previous `godot_delivery.py` still validates and exports the complete original source 2D PNG action sequence and physics project. In the ADDITIONAL Godot scene, the actual original `CharacterBody2D` actor, route, collisions, true animation action selection and source timing are retained. SpriteStack2D uses exactly the four-view sheet associated with the original currently selected full-body cel index. The original underlying `Sprite2D` is hidden **only in the new Godot scene**, not erased; it remains the timeline authority. Missing original stack for any body pose → fail; no stretch, skinned bone, rotating limbs or invented frames.
- **PixiJS/Matter.js/nipplejs/YUKA**: continue independently as the already existing browser physical gameplay exports, reusing original approved stacks where supported. This export does **not** claim to run PixiJS JS or YUKA inside Godot. Blender, APNG/WebP, Howler, FFmpeg and the official original animated GIF are preserved.

## Extra source metadata

Add `sprite_stack2d` to the **same original source** `scene.json` before running the full previous source gate. Existing `sprite_stacking` configuration is still mandatory, and every real actor clip retains the one-to-one `stack.json` per independently authored PNG full-body pose plus matching `source_pose_sha256`. The only supplementary fields are:

```json
"sprite_stack2d": {
  "directions": 16,
  "x_rotations": 65,
  "z_distance": 1,
  "shadow": true,
  "clean_plate": "environment/original_without_stacked_objects.png",
  "world_positions": { "gate_a": [240, 198], "tree_a": [310, 235] },
  "actor_offsets": { "hero": [40, 56] },
  "face_sheets": { "stacks/gate_a/stack.json": "original_views/gate_a_2x2.png" }
}
```

When original static objects are stacked, `clean_plate` is mandatory: it must be an original painted background **without** duplicate flattened copies of those same objects, at the exact source pixel size. It replaces the background only in the NEW Godot stack output, leaving the original Godot project ZIP unchanged. `world_positions` maps *each static original 3D object ID* to its separately authored 2D source-map coordinates. Never silently reinterpret 3D world coordinates as pixels. `actor_offsets` places the volume visual relative to the original `CharacterBody2D` sprite box; by default it uses half the original box. `face_sheets` is optional: its key is the actual referenced stack manifest path and its value is the original aligned 2×2 top/front/side/back RGBA PNG. When absent, the compiler derives the views deterministically from genuine source Z-slice pixels (no resampling/no painted fill). Source slices must be transparent, at least four different depth profiles, square 16–512 px, 8–160 slices and part of the original approved scene.

The existing `sprite_stacking` `environment_only=true` mode produces original 2D characters behind the newly stacked static props; a **full 3D actor cast** requires stacks for every original character and **every original full-body pose frame**. Coverage still obeys the original `coverage_min` >=0.75 (normally 0.90); the original eligible object roster cannot be trimmed just to make the number look higher. Some original rigid articulated parent/hinge props are not handled in native Godot SpriteStack2D mode: use existing independently implemented PixiJS or Three.js mechanism output for those. Never claim a clickable 3D gate in the native export without an actual source-authorized Godot gate controller.

## Full source-preserving build

```bash
python scripts/spritestack2d_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --fetch-addon
```

Or use `--addon-root /path/to/original/SpriteStack2D` without network. Optional `--godot /path/to/Godot` runs a genuine headless native import; installed **Godot 4.7** is recommended based on upstream's stated test target. The original `living_scene.gif`, `living_scene_assets.zip` and `living_scene_godot.zip` remain. An additional `living_scene_godot_spritestack2d.zip` contains the complete standalone Godot source project (including official MIT addon, original actors, frames, physics, authored 3D stack views and native startup scene); it is also linked inside the original asset ZIP. Nothing runs on mobile/desktop until the actual exported Godot project is opened by Godot; do not claim browser HTML or hosted game playability for this native export.

**Limit:** <=250 distinct 2×2 sheets and <=160 MiB of decoded RGBA views, to avoid unbounded mobile source memory. Default 16 cached rotation directions. Source scenes with more detail should supply genuine source LOD or use the original Three.js full-volume viewer; never silently downgrade the artist's approved source texture.
