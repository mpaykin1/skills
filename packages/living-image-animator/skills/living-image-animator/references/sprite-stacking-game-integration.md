# PixiJS gameplay bridge for existing Three.js Sprite Stacking FIRST — full-scene 2.5D volume from true authored 4-way orthographic art

**Priority for any game scene:** Use sprite stacking for as much REAL world geometry as available: architecture and interiors, walls/columns, trees, rocks, furniture, cars, machines, weapons, doors, bridges, enemies, monsters, and other moving characters. Keep far sky, lens/weather overlay, UI and suitable ground textures as normal source-painted environmental layers. Do not replace the user's existing grunge-horror paint, logos, exact characters or source meshes with cubes, primitive shapes, repeating voxel grids or generated substitute avatars. Do not claim an authentic 360 model from one frontal PNG.

Stacking is a **pseudo-3D** technique: colored, partly transparent horizontal PNG cross-sections positioned at different heights, seen at an elevated angle. The four orthographic source views are top, side, front, and back. This adapter calculates the intersection of their actual alpha masks. Each visible horizontal slice uses **real pixels from the source views**, preserving mottled rust, painterly edges, dirt and painted texture. Object yaw rotates the **complete** stacked 3D volume; it never rotates a detached limb or morphs an actor frame. It is not a conventional skinned 3D mesh. For Godot/Blender/Three.js interoperability, `--export-glb` emits real glTF 2.0 textured horizontal quads built by open-source trimesh; still source-alpha planes, not a substitute character rig.

## Live technology connection

```
Krita / OpenToonz / Pixelorama -> artist-approved FULL-BODY pose PNGs
SAM2 / MMPose / DeepLabCut -> unchanged actual original actor gate
Tiled / LDtk -> original world map, collisions, door sensors and routes
  -> Godot / Blender -> GIF 40–60s >=24 FPS + verified original source ZIP
  -> PixiJS v8 + PathFinding.js A* + Matter.js + nipplejs
  -> optional YUKA patrol/chase AI
  -> four-view alpha intersection + packed RGBA slice atlases
  -> SAME interactive game HTML with sprite stacks instead of 2D sprites
  -> optional exact-source 3D GLB pack for Three.js / Godot / Blender
```

The existing PixiJS source sprite still updates its original verified texture every animation step, even when hidden under the approved stack for that actor; the new stack swaps to the corresponding independent 3D volume for **that exact frame index**. No fake walk cycles, no static 3D actor moving as a stand-in. The original action pose/silhouette/gait/identity gate is not weakened. A character without source art for all 360 slice poses remains in the preexisting, fully functioning flat character HTML. If `sprite_stacking.mode=maximal` is requested and the inventory coverage falls below threshold, the stacking export **fails closed** instead of silently replacing missing art with synthetic boxes/cards.

Existing source scene variants for Howler, Rhubarb Lip Sync, FFmpeg, APNG/WebP, PixiJS Filters, particles, viewport, atlas, GLB, Godot and Blender **remain separately available**. This stacking physical HTML does not silently claim that the separate Rhubarb/Howler or weather shader pipeline is merged into the same document. It genuinely retains NPC AI if original source `scene.browser_ai.agents` selects YUKA. Only original four-view art turns into volume.

## Minimal authoring format

Add a `sprite_stacking_game` object to the same v3 `scene.json` (the prior `sprite_stacking` key remains reserved for the real Three.js GLSL raymarch renderer) that already supplies original animation actions, source actors, Tiled/LDtk maps and Matter sensors. Example stored in `examples/sprite-stacking.partial.json`.

```json
{
  "sprite_stacking_game": {
    "mode": "maximal",
    "minimum_coverage": 0.9,
    "clean_plate": "environment/scene_without_stacked_objects.png",
    "azimuth_deg": 35,
    "elevation_deg": 32,
    "inventory": [
      {"id":"hero","category":"actor"},
      {"id":"monster","category":"actor"},
      {"id":"gate","category":"door"}
    ],
    "actors": [
      {"actor_id":"hero","reference_view":"front","views_root":"stack_views/hero","slices":32},
      {"actor_id":"monster","reference_view":"side","views_root":"stack_views/monster","slices":40}
    ],
    "objects": [
      {"id":"gate","position":[320,260],"slices":48,"step_px":1,
       "open_trigger":"gate_sensor","collider":[310,242,20,36],
       "states": {
         "closed":{"top":"stack_views/gate/closed_top.png","side":"stack_views/gate/closed_side.png","front":"stack_views/gate/closed_front.png","back":"stack_views/gate/closed_back.png"},
         "open":{"top":"stack_views/gate/open_top.png","side":"stack_views/gate/open_side.png","front":"stack_views/gate/open_front.png","back":"stack_views/gate/open_back.png"}
       }}
    ]
  }
}
```

### Actor viewpoints — one extra view naming convention

For every **already-approved** `actors[].clips[].frames[].png`, the existing image is used **byte-for-byte** as `reference_view` (front/side/back). The other three genuine views are looked up automatically as:

`{views_root}/{action}/{stem}_{view}.png`.

For example, an approved `hero_run_000.png` in action `run`, source `reference_view=front` and `views_root=stack_views/hero`, requires `stack_views/hero/run/hero_run_000_top.png`, `..._side.png` and `..._back.png`. Every source frame must have these complementary 3 views, drawn **as the same character in the same action pose**, same identity/proportions/clothing and consistent orthographic x/depth/height. **Never copy one angle into other angles.** If any view is missing, fail this additional export. The original fully painted GIF and non-stacked gameplay remain available.

The four source images use transparent PNG: top dimensions `(width × depth)`, side `(depth × height)`, front and back `(width × height)`. Back is viewed from behind, facing the object (automatically mirrored into shared world x), source images are not silently stretched; `allow_resample=true` is an explicit nearest-neighbor-only opt-in. Source dimensions 8–512. Each volume has 8–96 actually carved layers, default 32, and at least three distinct cross-sections. Flat disks and four copies of the same PNG cannot qualify.

For a static weapon/house/car/prop, author the same four PNGs in `objects[].views`. Animated door/interior/vehicle mechanics use multiple truly drawn `objects[].states`, no rotation of missing prop parts. `open_trigger` must reference an **already-authored Matter sensor ID** in source `scene.matter.sensors` and `collider` exactly match original Godot obstacle. Only after an actual sensor enter does it switch to the original open sprite-stack state **and remove the exact barrier from Matter**; the player can pass. Closed/open states must share original volume dimensions. No fake opening animation if intermediates not authored.

**Clean source world:** If original objects are turned into stacks, supply original full-resolution `clean_plate` with those flattened object depictions already removed by the artist. It must match the original picture dimensions. This prevents superimposed ghost duplicate buildings or vehicles. Don't remove source-approved painted characters behind their back; the original upstream GIF and original ZIP are unchanged. Tiled/LDtk depth/terrain art remains optional and source-verified.

## One final command

```bash
python scripts/sprite_stacking_delivery.py original.png --scene scene.json --out result \
  --seconds 48 --fps 24 \
  --fetch-pixi --fetch-pathfinding --fetch-matter --fetch-nipple \
  --fetch-yuka --export-glb
```

Only specify `--fetch-yuka` when actual `scene.browser_ai.agents` exists. If source has no NPC AI, omit `--fetch-yuka` and the result still has original Matter + PathFinding + nipplejs physics and an actual 3D stack. Use `--pixi-js`, `--pathfinding-js`, `--matter-js`, `--nipple-js`, `--yuka-js` to supply authentic local pinned JS if npm/network is inaccessible. Browser output itself has **no CDN or online runtime requirements**. For source `sprite_stacking.objects`, real `clean_plate` and 4-view art are mandatory. Original artist input files are always required, never silently auto-generated from one photo.

`sprite_stacking_slicer.py` also works by itself on four genuine PNGs:

```bash
python scripts/sprite_stacking_slicer.py --top top.png --side side.png \
  --front front.png --back back.png --slices 48 --out gate_stack_atlas.png
```

`--export-glb` optionally imports open-source **trimesh (MIT)** and emits `living_scene_sprite_stacking_glb.zip` containing real alpha-textured 3D planar cross-sections for every static object state and one reference pose per stacked actor. `--all-poses-glb` includes **all** original approved actor pose stacks for a downstream 3D animation authoring pipeline. Standalone GLB is an asset, **not** proof of a working game or automatic animation retargeting. It may be loaded by Three.js GLTFLoader, Blender or Godot; the original PixiJS engine remains the physical in-browser player. No exact source character sprite is ever regenerated or replaced by a primitive mesh.

## Original open-source references and licenses

- Authentic independent four-view silhouette carving approach: Daniel White, `danielwh2/sprite-stacking` — MIT: https://github.com/danielwh2/sprite-stacking . New bridge and slicer here are separately written source programs, not a fake vendored copy of the original tool. Preserve upstream attribution for reference.
- Existing genuine PixiJS 8 engine — MIT: https://github.com/pixijs/pixijs . The new game mode **reuses** its already-embedded real engine rather than fetching or faking another one.
- Existing genuine Matter.js, PathFinding.js, nipplejs and YUKA keep the same exact pre-approved source asset/collision/motion hierarchy and license notices.
- Optional real trimesh glTF export — MIT: https://github.com/mikedh/trimesh . No external network/GPU required for GLB export when it is already installed.

**Quality policy:** Exhaust genuine original source views and layer coverage before considering any flat fallback. Full 360° yaw controls Q/E and touch turn buttons, pitch R/F and touch elevation buttons; motion uses original approved 24fps+ source pose sequence and real Matter body. Maximal mode requires >=90% of **declared** volumetric inventory covered by authored stacks (configurable 75..100%), a consistent actor pose-specific 3D volume, source-aligned clean environmental plate and no forged views. Because only declared inventory is measurable, the author must register every visible eligible object for the coverage metric to be meaningful. No substitute visual evidence and no unsupported claim about browser performance without actually executing the final scene.

## Direct reuse of already-installed true Three.js source stack packs (no duplicate drawing)

**Preferred source** is the EXACT same `stack.json` and original transparent Z-slice PNG files already consumed by `scripts/sprite_stack_delivery.py` and `scripts/sprite_stack_asset_preview.py` in the installed **Three.js 0.187.0 GLSL Data3DTexture** integration. The new `sprite_stacking_game` key does not overwrite that old `sprite_stacking` schema or source. To reuse a genuine stack pack:

```json
{
 "sprite_stacking_game":{
   "mode":"maximal", "minimum_coverage":0.90, "sampling":"linear",
   "inventory":[{"id":"hero","category":"actor"},{"id":"gate","category":"gate"}],
   "clean_plate":"environment/clean_plate.png",
   "actors":[{
     "actor_id":"hero", "slices":32,
     "clips":{
       "walk":["stacks/hero/walk/000/stack.json", "stacks/hero/walk/001/stack.json"],
       "idle":["stacks/hero/idle/000/stack.json", "stacks/hero/idle/001/stack.json"]
     }
   }],
   "objects":[{
     "id":"gate", "position":[250,200], "slices":32,
     "states":{"closed":{"stack":"stacks/gate/closed/stack.json"},"open":{"stack":"stacks/gate/open/stack.json"}},
     "open_trigger":"gate_sensor", "collider":[240,190,20,20]
   }]
 }
}
```

The pose array above is schematic: include **every** real original clip and **every** independently approved source frame (at least 12 frames per action); a two-frame example does not pass. Each source actor `stack.json` must contain `source_pose_sha256` equal to the original PNG's SHA256, and the `layers` are real relative PNG paths with 8–96 matching dimensions and >=4 distinct original cross-section silhouettes. A Three.js 160-layer pack remains valid in its old 3D viewer; for Pixi mobile game use a separately approved actual 32–96-layer authored LOD pack, not silently decimated or replaced source geometry.

The generated Pixi physical game uses the same source stack images; the original true 3D shader viewer continues to use them with full 360 3D raymarch. Do not say the Pixi pseudo3D renderer itself is a full raymarched 3D volume. Both routes share the source/cast validation and can independently open their authentic 3D authored objects. On one scene, **Three.js (`sprite_stacking`) and Pixi physics (`sprite_stacking_game`) may coexist** in the same source `scene.json`, producing separate authentic offline outputs with no false physics/audio merges.

`sampling="linear"` is the default for physically weathered, painterly Grunge Horror textures without visible pixel-grid edges; set `"nearest"` only for intentionally pixelated styles. Both preserve untouched original PNG bytes. The extra mobile physical build archives its actual original stack.json and each source PNG layer into `project/sprite_stacking/original_views/` inside the source ZIP with SHA256 manifest, allowing all connected toolchains to reuse the same exact original artwork.
