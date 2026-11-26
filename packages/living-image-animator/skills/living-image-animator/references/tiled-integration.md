# Tiled Map Editor → Godot 4 → Blender Grease Pencil 2.5D

Upstream: https://github.com/mapeditor/tiled . Official format: https://doc.mapeditor.org/en/stable/reference/json-map-format/ . Tiled is a separate GPL-licensed level editor; **the editor binary, tilesets and application are not copied into this skill**. Use its native editor to author annotations, then **File → Export As → JSON** (or the installed editor's `--export-map` CLI). The bridge parses official exported JSON; it does **not** invent collision geometry, infer walkability from imagery or render Tiled tile layers.

## Real integration

The new `scripts/tiled_bridge.py` is called **automatically by `godot_delivery.py`**, inside the existing `blender_delivery.py` pipeline, after the unchanged original full-pose animation gate and before Godot/Blender project generation:

`SAM2 → MMPose/DeepLabCut/ControlNet Aux → Krita/OpenToonz/Pixelorama → original painted PNG pose gate → Tiled geometry + registered alpha depth → Godot 4 navigation/physics → Blender 2.5D source kit`.

Input: `scene.json` (the existing complete sprite/actor scene) with optional `tiled` metadata, Tiled map exported to `.json`, original-size externally authored transparent PNG image layers. Output: a scene ZIP with validated Tiled-derived `godot.walkable_polygons`, `godot.obstacles`, `godot.navigation_actors`, `godot.layers` and `blender.layers`. The existing Godot 4 bridge creates NavigationRegion2D, NavigationAgent2D/CharacterBody2D, and StaticBody2D; the Blender bridge adds source-faithful depth planes. Original verified sprite PNGs and animation validation are not altered. The Tiled map JSON, source scene and original alpha planes are embedded in `living_scene_assets.zip` under `project/tiled/` and `project/inputs/tiled_layers/`.

## Authoring contract

- The Tiled exported map MUST be finite **orthogonal** with width*tilewidth and height*tileheight exactly equal to original uploaded image pixel dimensions. For isometric/hex maps, author a projection adapter first; **never** silently treat their coordinates as screen pixels.
- Create top-level `Object Layer` names for walkable polygons, obstacles and named point waypoints. Walkable objects are unrotated rectangles or Polygon objects; obstacles must be unrotated axis-aligned rectangles. For waypoints, use point objects (`point: true`) with unique nonempty names.
- Create optional top-level Image Layers with *exact* original source image size, position and offsets zero, opaque layer opacity and genuine PNG alpha. Individual image pixels need transparency; DO NOT rescale/warp.
- Tiled tile layers, tile collision metadata, nested groups, rotated geometry, project aliases, dynamic parallax transforms and non-orthogonal projections are **not** inferred by this bridge; explicitly draw/annotate object/image layers. Strictly fail on unsupported geometry instead of guessing.
- All paths are scene/map-root-relative and confined to the project; no URLs, path traversal, or absolute paths. Preserve image/cel identity, original native source paths and all character action frames.
- For interactive Godot navigation, a named `tiled.navigation_actors` actor MUST be present in the verified roster with at least one independently drawn and passed walk/run clip plus non-moving activity; waypoints must sit inside authored walkable polygons. Godot generates avoidance/physics, but no additional directional character drawings. Turning needs genuine existing left/right/front/back poses.

## Scene schema

```json
{
  "tiled": {
    "map_json": "maps/house.json",
    "walkable_layer": "Walkable",
    "obstacle_layer": "WallsAndTables",
    "waypoint_layer": "NPCWaypoints",
    "navigation_actors": {
      "cat_a": {
        "waypoint_names": ["cat_start", "cat_stairs", "cat_start"],
        "speed_px_s": 28
      }
    },
    "image_layers": [
      {"layer":"ForegroundCherryBlossoms", "z_index": 40},
      {"layer":"BalconyRail", "z_index": 25}
    ]
  }
}
```

All other required actor metadata remains in the original scene. The map JSON contains `objectgroup` layers with `objects`, and `imagelayer` layers pointing to source-local PNGs. `waypoint_names` must correspond to named Tiled **point** objects. `z_index` is the existing positive-forward ordering used in Godot and Blender; do not claim 3D parallax automatically generated or collisions imported from arbitrary tile GIDs.

## Mandatory final command

```bash
python scripts/blender_delivery.py source.png --scene scene.json --out output \
  --seconds 48 --fps 24
```

For native `.tnz`/`.pxo` inputs, additionally supply installed editor executable flags. For Godot/Blender runtime checks, supply `--godot` and `--blender`, respectively. Tiled itself need not be installed to **import a valid previously exported JSON map**. Without validated authored PNG poses, Tiled will not create a walking animation and the upstream release must still fail closed. If the Godot/Blender binaries are absent, only reproducible project sources are created — not a certified playable game or native `.blend`.
