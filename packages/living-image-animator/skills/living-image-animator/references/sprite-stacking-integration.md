# Sprite Stacking FIRST — true 3D volume for Living Image Animator v0.36

Official open-source GPU runtime: [Three.js](https://github.com/mrdoob/three.js), MIT, pinned `three@0.187.0`. Independently available author tool: `Sprite Stacking Grunge Horror` skill (source-painted `stack.json` + transparent Z-sections).

**Rendering architecture:** 3D authored XY slices at successive +Z heights become a real `Data3DTexture` with the exact pixel color/alpha in XYZ. GLSL 3 fragment raymarch casts each camera ray through the **entire** original source volume, finds the first opaque surface, shades it gently, writes the actual intersection depth via `gl_FragDepth`, and applies atmospheric fog by distance. This preserves the same source object at 360° azimuth and ±89° elevation, including back/side/top/bottom; unlike stacked Z-oriented `PlaneGeometry`, the object does not disappear edge-on. All original source PNG bytes are embedded for a true offline HTML once the genuine upstream ESM runtime has been packaged. Never claim WebGL1/iOS Safari rendering on an untested device. Use explicit user-provided LOD when mobile GPU budgets require it; NEVER replace detailed source with procedural cubes.

## Inputs: source geometry is mandatory

The original **already-approved** `scene.json` additionally declares `sprite_stacking`. This is checked for byte-equivalent JSON content against the original compiled `scene.json` inside the previously validated asset ZIP. Original `inventory`, `motion_gate.json` and every full-body pose PNG remain unchanged.

```json
{
 "sprite_stacking": {
  "enabled": true,
  "environment_only": true,
  "coverage_min": 0.9,
  "eligible_object_ids": ["archway", "north_gate", "lamp_01"],
  "camera": {"azimuth": 35, "elevation": 30, "distance": 150, "target": [0,0,0]},
  "objects": [
   {"id":"archway","kind":"architecture","stack":"stacks/archway/stack.json","position":[0,0,0]},
   {"id":"north_gate","kind":"gate","stack":"stacks/gate/stack.json","position":[12,0,0],
    "motion":{"type":"hinge","axis":"z","degrees":-100,"duration":1.7,"trigger":"click"}},
   {"id":"lamp_01","kind":"prop","stack":"stacks/lamp/stack.json","position":[6,8,0]}
  ],
  "actors": []
 }
}
```

Original stack manifest schema (same as Sprite Stacking Grunge Horror):

```json
{
 "size":128,
 "spacing":[0.125,0.125,0.125],
 "pivot":[0,0,0],
 "layers":["layers/000.png","layers/001.png","layers/002.png","layers/003.png","layers/004.png","layers/005.png","layers/006.png","layers/007.png"]
}
```

Above arrays are **only schema illustrations**, not generated art; files must exist. Slices are always transparent original PNG on the same square XY canvas; the first slice is bottom. Z+ upward; X+ right; Y+ forward (top of source PNG). 8–160 slices, 16–512 px XY, 256 MB uncompressed aggregate budget, no repeated file paths, at least four genuinely different silhouette/color sections. For detailed original model prefer 64–128 slices, 256–512 px XY, subject to actual memory. Pivots and pixel spacing are in consistent world units, not separate per-angle centering.

`eligible_object_ids` lists every source-authored eligible physical object (not sky, UI or screen effects), including any author-approved actors intended to appear in 3D. `coverage_min` is 0.75–1.0 and defaults to **0.90**. The exporter counts actual validated source stacks against that roster and fails if below threshold; do not manipulate inventory to pretend 100%. By default, a **full scene** also requires `eligible_object_ids` to include all approved actor IDs and requires all approved character pose stacks; if missing, **fail** rather than hide actors. Only an explicitly declared `"environment_only":true` renders a partial environment/asset inspection without actors and must not be called a complete game or full-scene cast. The sample above is environment-only for that reason.

## Animated actors — fully independent volume pose cels

For every actor in a full 3D cast, include exactly one independent approved 3D slice stack per **original full-body PNG cel** in each original source clip:

```json
"actors":[{
 "actor_id":"guardian",
 "position":[5,0,0],
 "yaw":0,
 "fps":24,
 "clips":{
   "idle":["stacks/guardian/idle/000/stack.json", "..."],
   "run":["stacks/guardian/run/000/stack.json", "..."]
 }
}]
```

Every `stack.json` must include `source_pose_sha256` = SHA256 of **the exact original approved corresponding full-body transparent PNG** from `project/inputs`. A single unchanged 3D texture may not be shifted, warped, bent or posed to fabricate another body action. Actor whole-volume pivots and sizes are identical for every frame; full 3D actor roster is all-or-nothing when including characters. The runtime defaults to safe idle/stand/rest or walk clip and supports explicit `window.__livingStack3D.setAction(actorId, action)` for true game-driven attacks/actions. It uses source-authored `locomotion.path` root travel for authored walk/run only. The 3D browser preview does **not** claim automatic linkage of YUKA AI, nipplejs or Matter.js: those remain independent existing game outputs until explicitly assembled.

## Original rigid multipart props / mechanisms

Doors and separate wheel/weapon parts can share authored object hierarchy (`parent` references an earlier declared object ID). Their individual stacks remain unchanged. Each `motion` may specify axis `x/y/z`, degrees, duration, `trigger:"click"` for gates or `trigger:"auto"` for continuously rotating mechanical sources. Open/close is possible by pointer/touch. These are rigid **physical part transforms only** and never satisfy any character pose gate.

## Export, real upstream dependency and honest limitations

`sprite_stack_vendor.py` pins real `three@0.187.0` and validates npm package name/version/MIT, extracting real `build/three.module.js` to embed inside one self-contained, CDN-free HTML. Local `--three-js` bypasses network. Browser must support **WebGL2/3D textures**; mobile capacity and actual FPS vary by source model and GPU. If there is only one front-facing photo, source-independent 3D geometry or separately authored Z slices are still mandatory: never call it a complete 3D scan. Link the approved Grunge Horror sprite stacking asset generator for Z source creation, not fake image extrusions.

**CLI:** `python scripts/sprite_stack_delivery.py source.png --scene scene.json --out output --fps 24 --seconds 48 --fetch-three` (or local `--three-js`). Output `living_scene_sprite_stacking_3d.html` and ZIP plus unchanged approved original GIF/PNG/Godot/Blender. Do not report the new viewer as tested on a specific device without an actual browser run.

### Direct preview of existing author-made stack packs

A genuine `stack.json` and original PNG slices from **Sprite Stacking Grunge Horror** can directly produce an independently checkable 360° Three.js asset viewer without changing existing LIA source actors: `python scripts/sprite_stack_asset_preview.py --stack path/to/stack.json --out asset_360.html --fetch-three`. The `asset_preview_only` flag is always true; this is not a full game/actor approval and preserves the source original PNG files. Actual official Three.js must be present to compile this offline HTML.
