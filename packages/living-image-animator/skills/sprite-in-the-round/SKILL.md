---
name: sprite-in-the-round

description: Genuine upstream sprite-in-the-round GLB/OBJ/VOX/16-direction PNG/turntable/HTML asset exports from the EXACT same author-approved Z-slice PNG volumes used by Living Image Animator, Three.js GLSL, Shader-Stacker and SpriteStack2D Godot. No fake geometry or animated-deforming actors.
---

# Sprite-in-the-round × Living Image Animator

Use this installed skill as a supplementary **static 3D sprite-stacking mesh/export route**, not instead of Living Image Animator's original hand-authored full-body animation, original GIF/source ZIP, collision, NPC AI, mobile controls or master `sprite-stacking` source scene. Mandatory integration specification: `../living-image-animator/references/sprite-in-the-round-integration.md`.

- Original MIT repository: https://github.com/SoAp9035/sprite-in-the-round pinned commit `1d842b4d6d4e7f26b13236dedaf5841ecbfec267`. `scripts/sprite_round_vendor.py` fetches and checks the **real** upstream `scripts/stack.py`, `glb.py`, `voxlib.py`, `assets/viewer.html`, original license. Never claim it was fetched if offline.
- Use exactly the same author-supplied stack manifests and bottom-first RGBA PNG Z sections already accepted for Three.js raymarch, PixiJS gameplay, SpriteStack2D native Godot caching and Shader-Stacker camera sorting. Do NOT invent material unseen in original reference, fabricate missing angles or fill in missing poses.
- Run `python ../living-image-animator/scripts/sprite_round_delivery.py source.png --scene scene.json --out output --fetch-round --fetch-three`. This executes unchanged previous original GIF/full-body gates and Three.js 3D viewer before producing **additional** mesh/VOX/OBJ and 16-direction art assets. For existing assets call `sprite_round_bridge.py --approved-zip ... --scene ... --out ... --upstream ...`, or `--stack` for isolated source asset preview.
- Enforce genuine approved source identity: every living actor frame retains separate correct whole-body `stack.json` and `source_pose_sha256`. Animated characters require many original complete pose stack files; static meshes cannot count as newly generated character action. Preserve per-pose original PNGs byte-exact and never warp/deform actors.
- Strict fail-closed on nonuniform voxel spacing, partial alpha that upstream would quantize, unreconciled inventory, missing external upstream source, wrong actor or source SHA, duplicate strips, unavailable GPU/native tools and missing original author art. Always retain the existing Godot and PixiJS versions; this module does not replace physics or animation.
