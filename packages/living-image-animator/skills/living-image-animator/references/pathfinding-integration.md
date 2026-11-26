# PathFinding.js × offline PixiJS × LDtk/Tiled/Godot (v0.21)

Upstream https://github.com/qiao/PathFinding.js — MIT license; pinned npm package `pathfinding@0.4.18`. It runs in a browser as `PF.Grid`, `PF.AStarFinder`, `PF.DiagonalMovement.Never`. Source: https://github.com/qiao/PathFinding.js/blob/master/README.md . No project code is surreptitiously copied without its license.

## Functional integrated pipeline

1. `ldtk_bridge.py` and `tiled_bridge.py` import separately authored navigation polygons, rectangular walls/obstacles, registered alpha depth plates and named routes. Their geometry is merged into verified `scene.json` fields `godot.walkable_polygons`, `.obstacles`, `.navigation_actors`. No arbitrary tile GID guessed as a wall.
2. Existing `godot_delivery.py` and `blender_delivery.py` enforce the complete full-body cel/MMPose/DeepLabCut/ControlNet Aux/SAM2 pipeline, then package the original motion-approved ZIP + GIF.
3. `pathfinding_bridge.py` consumes THAT verified ZIP only, validates actor identity and real authored walking clip, builds a bounded 4-neighbor orthogonal grid in original illustration pixel coordinates and checks authored waypoint reachability. `scene.browser_navigation.cell_px` is optional (integer 4..64; default 8). Obstacles are expanded by the actor's registered foot collision radius; truly blocked starts/targets fail closed, no teleportation or navigation through walls.
4. `pixijs_bridge.py` embeds genuine PathFinding.js browser runtime **only if** the final Godot/Tiled/LDtk data has navigation actors. `PF.AStarFinder({diagonalMovement:PF.DiagonalMovement.Never})` computes the route. PixiJS uses actual unmodified source PNG cel textures, frame-indexed moving/rest clips, world-position root steps, stable IDs, time-based speeds and authored waypoint loops. Static foreground and background alpha PNGs remain as before. This supplies dynamic **browser** A* avoidance, not Godot's collision solver.
5. PathFinding.js is OPTIONAL for a scene with no navigation actors. All prior still-to-GIF release gates remain mandatory and unchanged.

Install genuine library and builder using npm when internet is available:

```bash
python scripts/pathfinding_vendor.py --out vendor/pathfinding-browser.js
python scripts/pixijs_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24 --pixi-js vendor/pixi.min.js --pathfinding-js vendor/pathfinding-browser.js
```

Or pass `--fetch-pixi --fetch-pathfinding` when local npm+network are available. Engine libraries are embedded into one standalone HTML and never fetched from a CDN during playback. If npm is blocked, use previously installed authentic packages; **do not claim** the open-source distribution downloaded successfully or the HTML finished. No cutout warp, fake procedural actors or PFX substitutions. Correct facing/turn art still must be independently authored. This integration does not add new `.blend` or `.godot` binaries.
