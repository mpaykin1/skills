# Godot 4 — verified full-cel 2D/2.5D world exporter

Godot Engine: https://github.com/godotengine/godot — MIT license. Godot 4 docs: https://docs.godotengine.org/en/stable/classes/class_animatedsprite2d.html and https://docs.godotengine.org/en/stable/tutorials/navigation/navigation_introduction_2d.html . The engine is a **separate, optionally installed executable**. The skill bundles a project generator and original GDScript scripts, **not Godot itself**.

## Mandatory full pipeline

`godot_delivery.py` calls existing `controlnet_aux_delivery.py` **first**, which invokes SAM2 masks → MMPose human motion / DeepLabCut animal motion → Krita/OpenToonz/Pixelorama separately authored RGBA cels → existing physical locomotion and identity gates → GIF+ZIP. Only **after that pass** does `godot_bridge.py` create a real Godot 4 project using byte-identical transparent PNG frames, original actor IDs, full character action tracks, phase offsets, depth ordering and original world trajectory interpolation. The generated project's root includes `project.godot`, `Main.tscn`, GDScript actor/scene scripts, `data/scene.json`, `textures/`, and `sprites/`.

The Godot project is delivered separately as `living_scene_godot.zip` **and embedded** under `project/godot/living_scene_godot.zip` in `living_scene_assets.zip`. Original two deliverables remain `living_scene.gif` and `living_scene_assets.zip`.

### Timeline mode: strict GIF parity

By default, every actor replays **all** genuine authored PNG frames without interpolation, deformations, bone rotation, morphs, or character warps, using its own `phase_frames` and validated `locomotion.path`. The GDScript applies the same continuous cubic easing to actor **position only** as the GIF renderer. Character images remain exact. This mode is intended for deterministic playback of the artwork and does not invent collisions or navigation around unmarked walls.

### Interactive navigation mode: real Godot physics

Only for explicitly authored `scene.godot.navigation_actors`, the generator attaches a `NavigationAgent2D`, `CharacterBody2D` with collision shape, and navigates via `get_next_path_position()` / `move_and_slide()` every physics tick. Requires human-authored, nondegenerate and valid `walkable_polygons` and `waypoints`, as well as the actor's already validated original walk/run sprites; never approximate geometry from a screenshot. Authored `godot.obstacles` produce real `StaticBody2D` rectangular collision shapes. This gameplay navigation can adapt to collisions and **is not frame-exact identical to the pre-rendered GIF**. Avoid claiming foot-plant physics proved just because navigation is present. Draw directional turns separately; this bridge does **not** generate extra side/back cels.

## Optional source scene schema

```json
{
  "godot": {
    "walkable_polygons": [ [[20,300],[300,300],[300,390],[20,390]] ],
    "obstacles": [ [120,335,25,20] ],
    "navigation_actors": {
      "cat_a": {"waypoints": [[35,350],[240,350],[35,350]],"speed_px_s":35}
    },
    "layers": [
      {"png":"layers/foreground_tree.png","z_index":40}
    ]
  }
}
```

`godot.layers[].png` must be a genuine source-registered full-canvas image from the validated asset ZIP. It must not obscure incorrectly rendered character sprite limbs. `box`, `path` and waypoints use **original source-pixel coordinates**. For `navigation_actors`, waypoints refer to actor root's scene position; keep them inside the authored walkable polygon and away from obstacles.

## Command

```bash
python scripts/godot_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24
```

Pass optional `--godot /path/to/godot4` to run a headless Godot editor import check and reject GDScript/parsing problems. Without Godot installed, Godot project file creation and packaging still work, but actual Godot runtime correctness is **not** certified. To get a playable HTML5 link would separately require Godot web export templates, browser validation and hosting; **do not claim a playable web game is published merely by exporting a project**.

No user-facing reports or handoffs. If the new stage fails, do not label the complete animation delivered.
