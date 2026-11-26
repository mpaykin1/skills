# YUKA 0.7.8 — source-faithful NPC behavior with Matter.js and PathFinding.js

**Official upstream:** https://github.com/Mugen87/yuka — MIT; npm `yuka@0.7.8`. Uses the published genuine browser UMD `build/yuka.js`, which is embedded in the final single-file HTML. Requires npm/network only at build time, or a previously installed authentic UMD. The adapter does not contain or imitate the engine.

## Functional integration

1. First execute the unmodified `scripts/nipplejs_delivery.py` pipeline: authentic source image, author-painted independent 2D/2.5D poses, full per-actor identity/anatomy/action/gait and seamless-loop release checks, GIF+source ZIP, Tiled/LDtk geometry, Godot/Blender, true PixiJS8 A*, Matter.js collisions and nipplejs fixed touch joystick. **No prior gate may be skipped.**
2. `scripts/yuka_bridge.py` rechecks the same original ZIP via `matter_bridge.validate_scene()` and `nipplejs_bridge.read_controls()` and verifies that each AI actor ID exists in the approved original cast and author-registered navigators. The player controlled by nipplejs can never be reused as an autonomous NPC. **Missing original actors cannot be fabricated.**
3. YUKA `Vehicle`, `SeekBehavior` and `Vector3` steer NPCs along **real PathFinding.js A\*** grid routes on the existing Tiled/LDtk/Godot authored collision map. YUKA owns agent states and suggested velocity; **Matter.js remains the sole solver of actual physical contacts**. The engine always syncs its virtual vehicle position to the real Matter body before computing steering, avoiding parallel unsynchronized simulations. Actors are never teleported through walls.
4. Optional authored `mode: "patrol_chase"` allows a verified NPC to detect the actual player inside a bounded world-pixel radius, with original static wall line-of-sight blocking detection. The NPC requests a new **A\*** route to the moving player on a bounded cadence (>=0.25 seconds), then returns to its original verified patrol waypoints when the player escapes or remains out of sight long enough. `mode: "patrol"` simply smooths original NPC movement. Only source-authored waypoint routes are used; no generated level or geometry is accepted.
5. The existing source PNGs, full-cel frame selection, pose timing, sprite dimensions, actor IDs, original background/foreground, environmental FX and old exports stay untouched. The new AI physics game is an **additional** `living_scene_pixi_ai.html` + ZIP. Camera, 2.5D filter, GPU tiles, audio, FFmpeg and WebP outputs from the other entrypoints are not silently claimed to run in this particular HTML. Real front/back/left/right poses must be painted separately if directional movement changes.
6. The AI runtime is bounded to at most **12** authored NPCs, fixed-step **60Hz** movement and author-set 0.25–3-second pursuit re-path cadence. When YUKA, source artwork, source map or any pinned original engine is absent, fail transparently; never substitute a fake behavioral script or CDN.

## Authoring input

Add this to the original `scene.json` after existing `browser_controls` and authored `godot.navigation_actors` / Tiled or LDtk map definitions:

```json
"browser_ai": {
  "agents": [
    {
      "actor_id": "guardian",
      "mode": "patrol_chase",
      "detection_radius_px": 95,
      "forget_radius_px": 170,
      "forget_after_s": 1.2,
      "repath_interval_s": 0.5,
      "speed_multiplier": 1.0
    }
  ]
}
```

`actor_id` must reference a **separate** original actor already present in `inventory.actors`, whose approved locomotion clips include complete moving and resting frames and who has at least two user-authored original patrol waypoints. `player_actor` is taken from the existing `browser_controls`. Up to 12 unique source-approved NPCs are allowed. Modes are `patrol` and `patrol_chase` only. Detection/forget radii must remain within scene bounds; speed multiplier is 0.5–1.4. Rectangular authored walls block line-of-sight. This is finite-state behavior, not neural inference or automatic drawing.

## Complete command

```bash
python scripts/yuka_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 \
  --fetch-pixi --fetch-pathfinding --fetch-matter --fetch-nipple --fetch-yuka
```

Preload genuine npm/UMD packages and use `--pixi-js`, `--pathfinding-js`, `--matter-js`, `--nipple-js`, `--yuka-js` instead of the `--fetch-*` switches to build with no network. The browser HTML remains CDN-free and fully offline **only when the genuine local scripts have been embedded and all upstream gates passed**. Include `references/LICENSE.yuka.txt` in both the AI package and the comprehensive source ZIP.

Actual browser rendering, FPS and public deployment require separate verification. A plugin release itself is not a hosted game.
