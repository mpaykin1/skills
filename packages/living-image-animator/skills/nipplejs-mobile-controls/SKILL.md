---
name: nipplejs-mobile-controls
description: Add genuine fixed mobile nipplejs 1.0.4 joystick and WASD/arrow gameplay to source-approved Living Image Animator 2D/2.5D characters with real PixiJS 8, PathFinding.js A*, Matter.js collisions, and preserved full-cel animation.
---

# nipplejs Mobile Controls — Living Image Animator gameplay integration

This skill extends `skills/living-image-animator/SKILL.md` (read and enforce the **original stricter full-body pose, source, identity, gait and source-pixel** contracts without relaxing ANY original rule). Use `skills/living-image-animator/scripts/nipplejs_delivery.py` as the final orchestration stage for a **new standalone physical game HTML**, not for the camera/FX, Howler audio or FFmpeg film variant.

1. Previous authentic full source-cel validation, 40–60s GIF/ZIP, source-Tiled/LDtk collision mapping, Godot/Blender asset exports, real PixiJS 8 and PathFinding.js A* and Matter.js 60Hz **MUST complete first** through the original `matter_delivery.py`. If there is no authentic separate walking/rest action or author-approved collision/navigation source, fail; never replace missing actor frames with static cutout motion.
2. `nipplejs_vendor.py` downloads and validates genuine original `nipplejs@1.0.4` Rollup UMD via official npm, preserving the source MIT attribution. Without npm/network use the original locally supplied `--nipple-js` browser bundle. Never fake the source project or silently use a CDN.
3. `nipplejs_bridge.py` creates another **fully offline** HTML from the already successful genuine physical player; the HTML includes an *immobile* bottom-left thumb joystick (not a roaming dynamic joystick), real Matter.js body velocity and collision, the original A* walkable grid, optional tap-to-move and keyboard WASD/arrows. Other NPCs preserve their original routes. The hero never teleports through walls. Source approved PNGs, actor IDs, animation timing and source collision geometry remain unchanged.
4. Animation variants may require independently authored front/back/left/right full-body source poses. This integration NEVER infers or fabricates directional art, and particles/camera movement never count as independent animation. The physical new HTML does not claim that the separate PixiJS filters, audio or camera are also embedded. Preserve all existing modes independently (Howler.js, APNG/WebP, FFmpeg, terrain culling etc.).

```bash
python scripts/nipplejs_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --fetch-pixi --fetch-pathfinding --fetch-matter --fetch-nipple
```

For exact schema, mobile constraints, licenses and build flags read `skills/living-image-animator/references/nipplejs-integration.md`. `scene.json.browser_controls` optionally defines `player_actor`, `joystick_px`, `deadzone`, `speed_multiplier`, `tap_to_move`, `keyboard`, `show_desktop`. A real game URL additionally requires real web hosting and browser verification. Do not claim the runtime has been launched unless that happens.
