# Original sprite-in-the-round × Living Image Animator: genuine mesh exports

**Open source:** https://github.com/SoAp9035/sprite-in-the-round, MIT, pinned git commit `1d842b4d6d4e7f26b13236dedaf5841ecbfec267`. Author: Ahmet Burhan Kayalı. Read the original upstream `LICENSE`; no distribution/rebranding of proprietary material. The upstream CLI `scripts/stack.py` and actual `scripts/glb.py`, `scripts/voxlib.py`, `assets/viewer.html` MUST be installed from the pinned GitHub revision. The plugin does **not** contain a fabricated reimplementation. The installer needs working git/network at build-time or a separately available verified source folder.

## Sprite stacking synergy — additional output, no replacement

The previously installed `danielwh2/sprite-stacking` creates authentic PNG Z layers from all four original views. `SpriteStack2D` caches derived rotating silhouettes in native Godot 4 and Shader-Stacker uses the same original bottom-first Z layers in native Godot 4. Three.js GLSL casts through that original RGBA volume; PixiJS uses the source stack sprites alongside Matter.js collisions, YUKA AI, nipplejs controls and PathFinding A*. **This new exporter consumes the exact same approved `stack.json` and original author-painted Z slice PNGs** and runs *genuine upstream* `stack.py` to produce static GLB, OBJ/MTL, VOX, 16-direction transparency PNG, turntable GIF (optional), 360° HTML viewer and preview sheets for asset editing and further scenes.

Nothing in sprite-in-the-round animates characters, deforms cels, replaces the original approved animation/identity checks, or upgrades the existing game runtime automatically. For original moving actors, one separate complete original 3D volume per corresponding approved full-body pose is mandatory; all independent frame volumes are keyed to original SHA256 and exported individually. GLB models are separate static meshes for source whole-pose frames, not a new skeletal-rigged animated GLB. Original transparent PNG files remain **byte exact**, included alongside all exported forms. Mesh exports may discard soft alpha and VOX palettes may quantize colours; the adapter rejects any partially transparent original pixels rather than silently changing soft art, and explicitly labels derived mesh output as *not lossless source art*. The source originals are always the authority.

## Format and limits

Original `sprite_stacking.objects[].stack` and `sprite_stacking.actors[].clips[]` must refer to genuine `stack.json` as already checked by `sprite_stack_bridge.stack()` (8–160 original nontrivial RGBA depth slices, one square XY dimension and consistent spacing/pivot; original pose SHA256 checks for actors). `sprite-in-the-round` assumes one voxel per original art pixel in X, Y and Z. Input source spacing must be isotropic within 2.5%; otherwise the adapter fails instead of scaling proportions falsely. Only fully transparent/fully opaque pixels accepted by this derived mesh exporter. Maximum 250 separate volume poses per scene and bounded 96 MB decoded per strip. The honest `eligible_object_ids` coverage must be at least 90%; when `environment_only` is false, every approved original actor must supply genuine complete individual whole-body 3D frames. The existing 40–60 sec/24+fps original character GIF and source ZIP remain mandatory.

## Build

```bash
# Install the TRUE pinned source with git (one-time, build machine online):
python scripts/sprite_round_vendor.py --out ./vendor/sprite-in-the-round

# Add mesh and directional outputs to a complete already-authored source scene:
python scripts/sprite_round_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --three-js ./vendor/three.module.js \
  --upstream ./vendor/sprite-in-the-round

# Optional 360 GIF turntables, keeping originals intact:
python scripts/sprite_round_delivery.py source.png --scene scene.json --out output \
  --fetch-three --fetch-round --turntable

# Only one original, source-painted stack for review (asset preview, NOT a whole game):
python scripts/sprite_round_bridge.py --stack stacks/vehicle/stack.json --out output/asset \
  --upstream ./vendor/sprite-in-the-round --turntable
```

The full `sprite_round_delivery.py` calls the existing complete `sprite_stack_delivery.py` before any new export: the original source character motion gate, GIF, asset ZIP, Godot and Blender projects and Three.js 3D HTML must pass. Then a separate `living_scene_sprite_in_the_round.zip` is written and appended into the original assets ZIP. It retains each source `stack.json` and every original PNG Z slice verbatim under `source_stack/`, with SHA256 metadata. Original `SpriteStack2D`, `Shader-Stacker` native Godot projects, Three.js and PixiJS asset/game outputs are NOT overwritten. The plugin itself does not host a playable game; build only when installed native dependencies actually exist.
