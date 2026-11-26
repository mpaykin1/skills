# LDtk × Tiled × Godot × Blender: source-registered levels

Official MIT-licensed editor: https://github.com/deepnight/ldtk . Authoritative native JSON schema: https://ldtk.io/json/ . This skill contains the **actual import adapter** (`scripts/ldtk_bridge.py`), not an LDtk executable or new editor license. **LDtk does not itself generate missing character animation frames**. The bridge only imports original approved, explicitly painted navigation and depth metadata after unchanged GIF/pose/identity quality gates.

## Scene JSON (exact schema)

```json
{
  "ldtk": {
    "project": "levels/house.ldtk",
    "level": "House",
    "intgrid_layer": "Collision",
    "walkable_values": [1],
    "obstacle_values": [2],
    "entity_layer": "Markers",
    "entity_types": {
      "walkable": "Walkable", "obstacle": "Obstacle",
      "waypoint": "Waypoint", "door": "Door", "stairs": "Stairs"
    },
    "navigation_actors": {
      "cat_a": {
        "waypoint_names": ["cat_start", "doorway", "cat_start"],
        "speed_px_s": 32
      }
    },
    "image_layers": [{"png":"layers/foreground.png", "layer":"Decor", "z_index":40}]
  }
}
```

- `ldtk.project` must be a real `.ldtk` JSON file. Choose one `level` by `identifier` or `iid`; omit only if a single level exists. The selected level `pxWid`/`pxHei` must exactly equal the original illustration. If `externalRelPath` is present, the exported external level JSON must exist under the LDtk project directory. MultiWorld `worlds[].levels[]` is supported; projecting several offset levels onto an image without a declared camera transform is intentionally forbidden.
- `intgrid_layer`: select an actual layer of `__type=IntGrid` with valid `intGridCsv`, `__gridSize`, `__cWid`, `__cHei`. One-to-one, explicitly selected `walkable_values` and `obstacle_values` group same-value grid runs into bounded axis-aligned navigation/collision rectangles. No guessed meanings. Pixel offsets/mismatches or >32 navigation polygons or >128 obstacle rects are blocked; edit/simplify map instead of weakening collision validation.
- `entity_layer`: actual `__type=Entities`. Explicit entity identifiers may mean Walkable rectangle, Obstacle rectangle, or Waypoint/Door/Stairs location. Entity location uses the original `px` and LDtk `__pivot`. Named markers use a `fieldInstances` string field `Name`; otherwise the exact LDtk entity `iid` is a stable name. Door/Stairs are **named route markers only**; no automatic portal teleportation or stairs 3D reconstruction. Actors traverse them only if authentic walk/run/stair cels and valid authored routes exist.
- `navigation_actors`: waypoint names must exist in LDtk entities, and any actor also configured in Tiled or `godot.navigation_actors` is rejected. Godot's existing navigation polygon checks require all waypoints to lie in valid walkable geometry. Motion and foot-contact gates remain unchanged.
- `image_layers`: explicit full-canvas RGBA PNGs, optionally linked to existing LDtk layer names. These are imported in Godot as foreground/background planes and in Blender as original-pixel orthographic planes; tile atlas/image reconstruction is **not** synthesized. Import fails for mismatched dimensions, opaque image or unsafe paths.

The bridge is invoked after `tiled_bridge.apply_tiled` and before `godot_bridge.compile_project` from `godot_delivery.py`. Output keeps original `.ldtk`, selected external level JSON, source image plates, and map metadata in `living_scene_assets.zip`. Previously approved character poses, GIF and motion gate retain their bytes. Tiled map source files and navigation survive; duplicate actor navigation is rejected to avoid accidental double movement.

Final command remains:

```bash
python scripts/blender_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24
```

External Godot 4/Blender binaries are needed for runtime `.blend` verification. LDtk standalone editor is needed for authoring/visually editing a native map, not to parse already saved JSON. For browser-playable results, a separate validated Godot web export and hosting are still needed.
