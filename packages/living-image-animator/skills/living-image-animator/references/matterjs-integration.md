# Matter.js 0.20.0 × PathFinding.js × PixiJS: genuine 2D browser physics

Upstream: https://github.com/liabru/matter-js ; v0.20.0 MIT: https://www.npmjs.com/package/matter-js/v/0.20.0 . API: https://brm.io/matter-js/docs/classes/Engine.html .

**Actual scripts:** `scripts/matter_vendor.py`, `scripts/matter_bridge.py`, `scripts/matter_runtime.js`, `scripts/matter_delivery.py`.

## Mandatory composition, no frame fabrication

- `matter_delivery.py` first executes existing `pixijs_delivery.py` (full SAM 2, MMPose, DeepLabCut, ControlNet Aux, original Krita/OpenToonz/Pixelorama poses, 24fps+ 40–60s GIF, Tiled+LDtk, Godot/Blender and PixiJS with PathFinding.js). Any failure blocks the physics export.
- `matter_bridge.py` **reads the previously approved** `living_scene_assets.zip` through the existing `pixijs_bridge.load_scene`. It insists `motion_gate.json.all_actors_pass=true`, stable actors, original PNGs and real `godot.navigation_actors` geometry derived from independently authored Tiled/LDtk/Godot level metadata.
- A verified original rectangle `[x,y,w,h]` in `godot.obstacles` becomes an actual **static Matter.js rectangle body**; every navigable actor obtains a **dynamic circular collision body**. A real 60Hz `Matter.Engine.update` resolves physical collisions; each character remains an **unaltered approved RGBA flipbook sprite**, following the resolved physics-body position. PixiJS renders, PathFinding.js A* chooses route, Matter.js resolves contacts. Collision avoidance never counts as independently painted or authenticated character animation.
- The original source-relative author waypoints and per-actor clearance-expanded PathFinding.js navigation grids remain mandatory. If a target is unreachable, no teleport is allowed. The first navigated character can receive a new valid A* destination by clicking/touching the browser canvas.
- Optional author `scene.matter.sensors:[{id:'stairs_east', type:'stairs', rect:[x,y,w,h]}]` creates actual Matter `isSensor` bodies (types: `door`, `stairs`, `checkpoint`, `trigger`). `collisionStart` and `collisionEnd` emit `living-image:trigger` browser events with actor ID and type. These are **gameplay events**, not proof that a new pose/cel or an automatic door-opening animation exists.
- Original other actors (not navigated) retain their validated independent GIF timeline and original root trajectories. Existing atlas HTML remains deterministic; physics is **explicitly** the additional `living_scene_pixi_physics.html` target. Prior HTML, original GIF, ZIP, Godot/Blender sources are preserved intact.
- Physics bodies follow the established current browser **top-left actor-root coordinate** used by prior PathFinding.js exports, not an inferred anatomical center of mass. Frame contact/weight shift is still validated by the original pose gate; Matter does not simulate skeletal anatomy.

## Real engine, local and offline

```bash
python scripts/matter_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24 \
  --fetch-pixi --fetch-pathfinding --fetch-matter
```

Or provide genuine existing engines `--pixi-js path/to/pixi.min.js --pathfinding-js path/to/pathfinding-browser.js --matter-js path/to/matter.min.js`. `matter_vendor.py` pins **actual** `matter-js@0.20.0` using `npm pack`, verifies original package manifest and MIT license, retains LICENSE and SHA256. Network is required only during build, **not playback**. Do not claim that npm download succeeded on a machine without internet; never create a fake physics/Canvas substitute or use a CDN. `matter_bridge.py` embeds genuine JS scripts and every original source frame as one standalone HTML.

**Limits:** users supply already-authored walking poses, door/stair visual frames (if desired), accurate collision shapes, waypoints and correctly oriented PNG art. Matter.js cannot draw limbs, infer physical rooms from a flattened PNG or generate new character perspectives. Actual browser frame rate and visible physics must be inspected in a running browser before claiming a published playable game.
