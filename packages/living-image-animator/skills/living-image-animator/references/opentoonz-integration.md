# OpenToonz ↔ Living Image Animator v0.8 (native 2D and layered 2.5D)

Source: https://github.com/opentoonz/opentoonz ; documentation: https://opentoonz.readthedocs.io/en/latest/rendering_the_animation.html and https://opentoonz.readthedocs.io/en/latest/editing_animation_levels.html .

**Real integration already available**: `opentoonz_bridge.py` runs OpenToonz's installed `tcomposer` on actual `.tnz` scenes. This v0.8 upgrade adds a zero-fallback preflight gate and fixes obsolete release guidance. This is an external binary integration, not vendoring OpenToonz. OpenToonz and embedded third-party licensing must be reviewed before redistributing external components.

## Art source contract

- Source art is always real, independently drawn full-figure OpenToonz cels. Separate human/animal identity per actor and maintain camera-box pixel registration. Do not synthesize 24 copies of one frame, rotate individual extracted body parts, morph the approved sprite or deform it to imitate motion.
- Every actor has 2+ named actions with >=12 cels per action; 8+ unique drawn poses; >=24fps final. Per-scene `inventory.actors` matches `actors[*].id`; each actor has a full-frame grayscale `source_mask` and fixed `box=[left,top,width,height]`.
- Create a native `.tnz` for each authored action (or use frame ranges in a coherent shared source scene), and preserve its linked drawing levels. Levels may be Toonz Raster/Vector or imported independent RGBA cels. Set source camera width/height **exactly** to actor-box width/height, transparent background, correct frame rate, with no camera drift.
- Draw true motion for horses (legs/body/tail/head), riders (hands/shoulders/arms), soldiers (recoil/aim/reload) and falls (separated inertial arcs and realistic contacts). Avoid cloned silhouettes, freeze holds, sliding hooves or changing costumes.

### Clip declaration in scene.json

```json
{
  "action": "shoot",
  "opentoonz_scene": "opentoonz/cowboy/shoot.tnz",
  "joints_json": "opentoonz/cowboy/shoot.joints.json",
  "start_frame": 1,
  "frame_count": 24,
  "dependencies": ["opentoonz/cowboy/drawings/cowboy.0001.png"]
}
```

`joints_json` contains one frame annotation per cels: `{"frames":[{"root":[20,38],"hand":[12,19],"elbow":[25,26]}, ...]}`. Use genuine image coordinates relative to the sprite box. Each joint must be finite, within the box and consistently named across frames. All paths stay relative to scene.json; include *every* linked source asset in dependencies (the bridge cannot automatically infer arbitrary alias-based project paths). Keep OpenToonz project folders and aliases resolvable during tcomposer rendering.

### Execution

```bash
python scripts/unified_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24 --opentoonz /path/to/tcomposer
```

Mixed `.tnz` and `.pxo` scenes additionally use `--pixelorama /path/to/Pixelorama`; `.pxo`-only scenes can omit `--opentoonz`. `OPENTOONZ_TCOMPOSER` and `PIXELORAMA_BIN` are accepted. Every source is independently checked before render. The existing bridge calls `tcomposer <scene.tnz> -o <frames..png> -range START END -step 1` as a subprocess and consumes the returned PNG sequence with true alpha; the strict pose compositor then builds GIF and ZIP. OpenToonz does not create missing drawings: artist-approved, independently drawn cels are a release prerequisite.

### Fail closed

Missing tcomposer binary, unavailable `.tnz`, missing linked levels, undeclared needed files, wrong-sized/opaque PNGs, insufficient joints, frozen actor, small motions, identity changes, short/corrupt output or broken loop => no finished GIF/ZIP claim. `--preflight-only` is a convenience for source validation, not a substitute for native render or final human visual inspection.
