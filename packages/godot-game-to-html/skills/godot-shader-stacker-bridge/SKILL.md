---
name: godot-shader-stacker-bridge
description: >
  Official MPL-2.0 x3cca/Shader-Stacker integration for authorized Godot 4 games:
  real existing RGBA stack.json, slice strips, original static GLB and four-view source
  art -> exact Godot single-column bottom-on-bottom atlas, original SpriteStack +
  StackCamera/Reset2D addon and independent editable Godot scene. Preserve original
  source, existing Three.js WebGL2 raymarch, Grunge Horror, Open3D and Unity toolchain.
---

# Shader-Stacker Godot 4 — integrated with META GAMES

The **real official upstream addon**, git SHA `21d86ab62140b0d08ea217982036e3cb184afed5`, is cached on first use and copied unmodified into a new Godot 4 project. MPL-2.0 license is copied with the addon. Original Godot/Unity project **not modified**; optional `--project-template` copies a full Godot project and preserves its `run/main_scene` and scripts, native WebGL remains the playable authority. Project is an **independent 2.5D visual preview**, not a port of scripts, logic, effects or physics.

## Module interoperation

- **danielwh2/sprite-stacking**: aligned top/side/front/back PNG → four-view hull → `stack.json` RGBA slices → Shader-Stacker. Missing depth is estimated, not exact source art.
- **SoAp9035/sprite-in-the-round**: its one-row `slices` PNG with embedded slice count can be read directly, without inventing layers; can also use resulting `stack.json`.
- **Sprite Stacking Grunge Horror**: existing bottom-first `layers/000.png...` + `stack.json` → one PNG, bottom slice in **bottom row**; colors and alpha exact, no extra quantization.
- **Open3D/trimesh + authored UnityGLTF/Godot GLB**: existing `stack_from_glb.py` first produces real volume slices, then same Godot output. GLB's original remains intact.
- **Godot Shader-Stacker**: official `SpriteStack` and `StackCamera` scenes, adjustable yaw/pitch and screen-height z-ordering. `Reset2D` remains available in addon. Camera Q/E or mouse drag rotates; WASD pans, wheel zooms; no auto attack, no invented animations.
- **Three.js + WebGL2**: original volume raymarch remains available and is the full spherical-angle visual preview; Shader-Stacker is specifically a 2.5D Godot runtime technique and does not replace it.
- **Khronos glTF Validator / Playwright / Pixelmatch**: unchanged; compare approved source and candidate browser visuals before promoting anything. 2.5D projection is not pixel-identical to full 3D.

## Commands

```bash
python skills/godot-game-to-html/scripts/shader_stacker_godot.py original/stack.json --out derivatives/godot-shader-stacker
python skills/godot-game-to-html/scripts/shader_stacker_godot.py model.glb --out derivatives/godot-from-glb
python skills/godot-game-to-html/scripts/shader_stacker_godot.py four-views.png --four-views --slices 64 --out derivatives/godot-from-views
python skills/godot-game-to-html/scripts/shader_stacker_godot.py slices.png --slices 36 --out derivatives/godot-from-strip
```

`--project-template /original/GodotProject` copies the entire original Godot project into `--out`, adds `generated/SpriteStackAssets.tscn` and enables the official addon without altering its start scene. `--addon /path/to/existing/ShaderStacker` uses locally available trusted official addon, `--no-install` disables any git fetch. Produces `project.godot`, actual unmodified `addons/ShaderStacker`, license, `generated/stack_XXX.png`, Godot preview `generated/Main.tscn`, reusable `generated/SpriteStackAssets.tscn`, and original-source SHA-256 manifest. Existing projects are **not overwritten**. Godot 4 is required to open/run output. Newly generated art for author-approved reference remains subject to original asset provenance rules. Because Godot Shader-Stacker supports 2.5D, perspective/lighting/pixel parity differs from volumetric GLSL.

## Exclusions

Animated full-body heroes and monsters are not generated from a single pose. Source animated GLB animations stay in the original engine/GLB viewer unless explicit complete pose frames are provided. If slice sheet contains multiple frames, the bridge fails instead of dropping them. No fake 3D reconstruction from one image, no generated replacement models, no automatic attacks.

Source: https://github.com/x3cca/Shader-Stacker (MPL-2.0). Use the pinned official source untouched; when shipping redistributable addon, preserve the full MPL-2.0 text and applicable notices.
