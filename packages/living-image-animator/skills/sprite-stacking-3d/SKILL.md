---
name: sprite-stacking-3d
description: Real multi-layer sprite stacking as the preferred 3D rendering for Living Image Animator. Build genuine 3D from independently authored transparent XY/Z PNG slices, render all camera angles via Three.js 3D texture raymarching, rigid articulated parts, and complete source-matched stacked full-body actor pose sequences. Preserve every original 2D/2.5D source identity, motion and animation gate.
---

# Living Image Animator — Sprite Stacking FIRST

This is an **ADDITIVE skill inside the existing Living Image Animator plugin**, not a new incompatible engine. **Always first read** `../living-image-animator/SKILL.md` and `../living-image-animator/references/sprite-stacking-integration.md`; its original anti-warp, identity, original art and full-body action rules are mandatory. All existing scripts and alternative PixiJS/Godot/Blender/Howler/FFmpeg/APNG/YUKA outputs remain valid and unchanged.

## Default rendering policy: maximum real sprite stacking

- **Prefer TRUE sprite stacking for EVERY suitable 3D object**: buildings, arches, bridges, gatehouses, rooms, columns, gates/doors, stairs, trees, vegetation clusters, furniture, guns, machines, wheels, vehicles, debris, monsters, weapons, collectible props, volumetric fog/cloud art, environmental silhouettes and individual animated full-body poses. A 2D background can remain a painting or sky where no honest volume source exists; UI remains screen-space. Do not model source-authored 3D elements as default BoxGeometry, voxel cubes or billboard impostors.
- Author **explicit object inventory** `scene.sprite_stacking.eligible_object_ids` and achieve >=90% genuine stack coverage (`coverage_min` defaults .9). The threshold is checked against the full original inventory, not a fabricated count. Full-scene output requires genuine full-pose stack volumes for **all** certified original characters. Explicit `environment_only:true` is allowed only for a clearly marked environmental preview; never hide missing actors in a claimed game. All source voxel/slice data must be real with alpha and actual changing cross-sections. Source-only scenes lacking real slices MUST be blocked for the 3D output; keep existing authentic 2D GIF instead of claiming a fake 3D reconstruction.
- Read and reuse author-owned skill `sprite-stacking-grunge/sprite-stacking-grunge` for original PNG slice generation when installed, retaining `stack.json` convention: `layers/000.png` bottom to top, shared XY, `spacing:[dx,dy,dz]`, `pivot:[x,y,z]`, `size`. Default 64–128 slices for detailed objects, authored source LOD for mobile where appropriate. Different 3D angles must be one and the same complete volume. Do NOT use independently drawn 3D views as pretend slices, or repeatedly clone the same PNG.
- **Characters:** original complete approved painted PNG cel action sequences remain mandatory. For 3D characters author a **different complete genuine stack for EACH approved full-body pose**, for EVERY original action; prove every corresponding 2D cel source SHA-256 in each pose `stack.json.source_pose_sha256`. Stable character volume box/spacing/pivot and correct texture identity across frames. At run time swap FULL volumes rather than warping faces/bodies. Never independently spin/twist a drawn hand/limb, invent missing poses or auto-trigger attacks. Existing 2D sprite modes remain available separately if 3D stacks are missing.
- Gates, weapon attachments, wheels, portals: distinct author-made 3D stacked parts may rotate as **rigid** whole components around a fixed pivot. A user click can open authored gates. No procedural body rigs. Use `scene.sprite_stacking.objects[].motion` for `hinge` or `spin`, with explicit `trigger` (`click` or `auto`); attack is never automatically triggered.
- Actual 360 camera orbit, free pitch above/below, mouse/touch, zoom, true light/depth/fog. Real volumetric rendering: official **Three.js 0.187.0** `Data3DTexture` RGBA + GLSL3 first-hit raymarching and `gl_FragDepth`. Not a few translucent 2D planes and not a 2D GIF billboard. A source stack is correctly visible from the side, beneath and above.
- Preserve original style: by default real-world proportions and grunge horror for newly made objects; for user references retain their exact source construction, materials and painterly look, even when not grunge. No repeated tile/pixel patterns or unapproved substitute source assets.

## Use the existing real art + source gate, then create the extra 3D file

`scripts/sprite_stack_delivery.py` calls existing `blender_delivery.py` first (original Krita/OpenToonz/Pixelorama + reference models + original independent whole-body PNG animation + GIF + source ZIP + Tiled/LDtk + Godot/Blender validation). Then `sprite_stack_bridge.py` validates every explicit authored stack, original actor source SHA, real metadata/coverage and pinned official Three.js and adds one MORE autonomous `living_scene_sprite_stacking_3d.html`, ZIP, and manifest. No CDN. Previous PixiJS/Howler/YUKA/physics/FFmpeg variants are **separate**, not automatically present in the new Three viewer. A playable source-accurate 3D scene requires authentic slice inputs and full browser verification.

```bash
python scripts/sprite_stack_delivery.py SOURCE.png --scene scene.json --out OUT \
  --fps 24 --seconds 48 --fetch-three
```

Or use `--three-js /path/to/official/three.module.js`. `sprite_stack_vendor.py` gets exact `three@0.187.0` from the official npm tarball and verifies MIT and version; it cannot fetch without network. Never claim binary available or source files created if not actually downloaded/generated.

## Expected deliverables

Actual new browser HTML from original RGBA 3D slice textures, complete original pose GIF, original asset ZIP and independent 3D ZIP. For user-provided full 3D packs, show actual 3D result and link to the artifact after it is built. Do not provide source-only descriptions instead of promised art. Do not invent public URLs or native engines. No unsolicited reports, tests, handoffs or evidence.

## Direct asset preview from the author's existing Sprite Stacking Grunge output

For any genuine independent `stack.json` with original painted PNG slices, inspect the same volume **without building a whole animated game first**:

```bash
python scripts/sprite_stack_asset_preview.py --stack ORIGINAL/stack.json \
  --out original_asset_360.html --fetch-three
```

Or `--three-js` using the official standalone ESM. This builds an actual 360° WebGL2 offline viewer from the source slices and shared pivot. It is explicitly an **asset-only preview**, does not claim approved human/animal motion, and preserves the original stack package. Never use it as proof a full scene/game is complete.
