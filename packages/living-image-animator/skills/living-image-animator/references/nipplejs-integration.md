# nipplejs 1.0.4 × PixiJS 8 × Matter.js × PathFinding.js

**Original source**: https://github.com/yoannmoinet/nipplejs (MIT), `nipplejs@1.0.4`. The release has an official Rollup UMD browser bundle at `dist/index.min.js` (fallback `dist/index.js`). NPM and git sources remain external; this plugin contains adapters and the authentic license, never a mock nipplejs.

## Native 2D/2.5D physical gameplay

- `nipplejs_delivery.py` calls **the unmodified** `matter_delivery.py` FIRST: approved Krita/OpenToonz/Pixelorama/SAM2/MMPose/DeepLabCut 2D full-body PNGs; full 40–60s 24+ FPS genuine GIF, ZIP, original Godot/Blender source, genuine PixiJS 8, genuine PathFinding.js A*, and original Matter.js obstacle/physics browser export. Nothing skips the prior art, identity, gait, contact, action or no-deformation checks.
- `nipplejs_bridge.py` checks the approved ZIP and real Matter HTML again, then inserts the authentic `nipplejs` UMD into **a new** self-contained HTML with a permanent bottom-left mobile touch joystick. Existing `living_scene_pixi_physics.html`, GIF, source ZIP and all other separate HTML variants remain unchanged.
- In the NEW `living_scene_pixi_controls.html`, the original Matter.js body moves under keyboard arrows/WASD or the touch joystick's authentic vectors. The scene's source-pixel walkable A* grid blocks manual movement through disallowed cells; Matter.js static colliders remain authoritative. When the player is stationary, the actor returns to its genuinely painted rest/idle frames; no invented or warped poses. Other NPCs continue their original A* loops. Click/tap on the rest of canvas can instruct a valid A* route for the selected player, immediately overridden by joystick/keyboard input. No teleport or canvas substitute for a full-cel character.
- `nipplejs` uses a **fixed** 120px default joystick, intentionally not dynamic/follow mode, so controls do not jump around the phone. The joystick is rendered on touch-capable devices; optionally also on desktops. Touch zone is separate from the canvas pointer route handler and respects iPhone safe-area insets.
- The CLI fails visibly when official npm/UMD packages, real hand-authored map, true source artwork or motion gate are missing. No CDN, network, paid dependency or fake joystick in the resulting HTML. Runtime browser, frame rate and game URL require actual separate runtime verification and hosting.
- Limitation: existing schema provides walk/run/rest clips, but not automatic directional sprite view selection; the original artist must explicitly paint actual front/back/left/right full-body poses if needed. No 3D physics or combined full-scene viewport FX is silently claimed inside this physical player; the other camera/FX/player outputs stay separately available.

## Command

```bash
python scripts/nipplejs_delivery.py source.png --scene scene.json --out output \
  --seconds 48 --fps 24 --fetch-pixi --fetch-pathfinding --fetch-matter --fetch-nipple
```

To avoid npm, supply `--nipple-js /path/to/authentic/index.min.js`, `--pixi-js /path/to/pixi.min.js`, `--pathfinding-js /path/to/pathfinding-browser.js`, `--matter-js /path/to/matter.min.js`. The `LIA_NIPPLEJS_BUNDLE` environment variable is also recognized. Only the actual source engines are embedded; no CDN at runtime. Original MIT license is included in both output ZIPs.

## Source-authored control options

In the original `scene.json` (optional):

```json
"browser_controls": {
  "player_actor": "hero",
  "speed_multiplier": 1.0,
  "joystick_px": 120,
  "deadzone": 0.13,
  "tap_to_move": true,
  "keyboard": true,
  "show_desktop": false
}
```

`player_actor` must exactly match an existing approved `godot.navigation_actors` character imported directly or through Tiled/LDtk. When omitted, the first registered navigable actor in original cast order is selected. Original waypoints, maps and validated sprite PNGs remain untouched.
