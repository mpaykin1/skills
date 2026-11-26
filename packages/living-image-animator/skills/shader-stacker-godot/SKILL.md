---
name: shader-stacker-godot
description: Additive real Shader Stacker 4.x (MPL-2.0) Godot 4 integration for Living Image Animator. Converts verified PNG Z-slices/stack.json into one-column Godot SpriteStack sheets and a separate working project with StackCamera sorting. Preserves original full-body RGBA actor poses, animation gates, Three.js GLSL and PixiJS/YUKA/Howler.
---

# Shader Stacker × Living Image Animator v0.40

This is an **actually bundled native Godot 4 add-on** derived from the original upstream at https://github.com/x3cca/Shader-Stacker, revision `21d86ab62140b0d08ea217982036e3cb184afed5`, under MPL-2.0. Original GDScript engine, `plugin.cfg`, `init.gd`, source notice and license are included. Editor-only SVG icons are local functional replacements; character/sprite art is never generated. No network is needed to install the add-on after obtaining this plugin archive.

## How it strengthens existing open-source technology

- **Daniel White `danielwh2/sprite-stacking`**: real four-view carved strip -> original actual transparent PNG Z-slices, not a billboard.
- **Sprite Stacking Grunge Horror**: genuine authored `stack.json` with bottom-to-top PNG files, `size`, `spacing`, `pivot`. **This is the canonical shared asset format.**
- **Three.js/GLSL**: retains the separate full-volume 360° 3D raymarch viewer; Shader Stacker does NOT replace it, and its 2D draw routine has different camera behavior.
- **Godot 4**: `SpriteStack` receives same PNG slices packed into a **single column, bottom slice at bottom row**, exact RGBA round-trip; `StackCamera` sorts objects, `Reset2D` remains available for separately painted 2D nodes.
- **Original full-body animation**: original `godot_delivery.py` runs first, including all motion, identity, full 24fps+/40–60s anti-warp checks. For explicitly authored complete per-pose stacks, Shader Stacker swaps the *whole stack texture* in sync with the original character's currently selected original full-pose texture. Without complete per-pose stack references, it never fakes actor 3D.
- **Source world physics**: original Godot CharacterBody2D / NavigationAgent2D, navigation polygons and static collision objects continue unchanged. Stacks are presentation only and do not invent 3D collisions or mesh bones.

## How to use

Run `skills/living-image-animator/scripts/shader_stacker_delivery.py` on a genuine source image and approved scene config. It calls the entire existing `godot_delivery.py` first and then emits **another** Godot project ZIP containing the actual Shader Stacker addon. If the original full-validated GIF/Godot project already exists, use `shader_stacker_bridge.py` directly.

```bash
python scripts/shader_stacker_delivery.py source.png --scene scene.json --out output --fps 24 --seconds 48

# Or reuse already-passed source outputs:
python scripts/shader_stacker_bridge.py \
  --approved-zip output/living_scene_assets.zip \
  --godot-zip output/living_scene_godot.zip \
  --scene scene.json --out output
```

Optional `--godot /path/to/godot4` requests actual Godot native headless editor import; absent that binary, describe project as exported, not runtime verified. New output is `living_scene_godot_shader_stacker.zip`. Original ZIPs/HTML remain unchanged. The new `.godot` project enables the packaged add-on and chooses `StackWorld.tscn` as main scene. `Q/E` or pointer drag rotates the stack projections. Three.js still provides the true volumetric 360° view; Godot Shader Stacker is a 2.5D sprite-stack rendering mode.

The original scene must define `sprite_stacking.enabled=true`, an exact inventory including every 3D-eligible item, `objects[].stack` and optionally `actors[].clips`. `sprite_stacking.background` (or matching `sprite_stacking_game.clean_plate`) must be an artist-made original-size PNG without duplicate painted objects. At least 90% of declared eligible items need actual source stacks; optional higher author threshold remains respected. Each animated full-body actor needs all approved independent pose stacks, whose `source_pose_sha256` must match the original RGBA pose bytes. Missing real input => block and explain, never generate placeholder characters/props or bypass previous validators.

MPL-2.0 source and notices must accompany every distributed Godot addon; original GDScript remains separately redistributable source. Read `skills/living-image-animator/references/shader-stacker-integration.md` and `LICENSE.shader-stacker.txt`. No native Godot player or hosted game is claimed without running it.
