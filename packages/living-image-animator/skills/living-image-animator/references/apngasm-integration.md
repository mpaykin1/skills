# apngasm 3.x × Living Image Animator — actual transparent APNG

Official zlib-licensed code: https://github.com/apngasm/apngasm . CLI: https://github.com/apngasm/apngasm/blob/master/docs/man/apngasm.1 . A real external binary `apngasm` v3 is required; the plugin does not contain or pretend to have the binary.

## Relationship to existing engines

- Krita, Pixelorama and OpenToonz: source-authored individually painted **original RGBA PNG** poses remain completely unchanged. The existing full-frame pose validator still checks all people/animals, identities, independent actions, amplitude, feet, joints, contacts, >24FPS and anti-jerk. No skeletal warp or frame duplication to fabricate motion.
- `apngasm_delivery.py` calls the full original `blender_delivery.py` (therefore `godot_delivery.py` and original `controlnet_aux_delivery.py`/`unified_delivery.py` etc.) BEFORE APNG export. Original GIF, original source ZIP, Godot and Blender packages remain intact.
- `apngasm_bridge.py` reuses the strict `pixijs_bridge.load_scene()` and `motion_gate.json.all_actors_pass` to read approved original `project/inputs/...` PNG files from that same ZIP. Per actor it outputs a complete transparent APNG loop, with optional per-action APNGs. It never converts the palette-reduced GIF into APNG, because that would lose colors and alpha.
- CPU C++ apngasm converts original full-body RGBA images to APNG using infinite loop `-l 0` and exact rational `-d 1/<fps>` frame timing. The decoder independently checks visible RGBA pixels and alpha at every original frame midpoint, verifies frame duration and loop metadata, and refuses incorrect compression/quantization or static frames. Duplicate consecutive frames may be coalesced only if the original timing and visual sequence are preserved.
- Each `complete_cycle.apng` and optional `action.apng` can be used with `<img src="...">` or packed as base64 in a single-file HTML; no browser texture deformation and no WebGL requirement for native APNG playback. PixiJS renderer, atlas, PathFinding.js, Matter.js and tilemap are preserved **as their previous browser outputs**, not claimed to be replaced by this APNG exporter. For moving-world actor positions keep PixiJS/Godot root trajectories, since an APNG image alone does not implement physical navigation.

## Optional automatic compilation / no GPU

`python scripts/apngasm_install.py --out vendor/apngasm` clones the **real** `https://github.com/apngasm/apngasm.git` source with git and builds via CMake + system libpng, zlib, Boost and C++ compiler. It records upstream git revision and copies original zlib license. This requires a network connection at build time; on an offline machine supply your existing authentic `apngasm` binary. No API key, GPU, npm, paid service or external online runtime is needed.

## Integrated command

```bash
python scripts/apngasm_delivery.py source.png --scene scene.json --out output \
  --seconds 48 --fps 24 --build-apngasm --per-action
```

Or use `--apngasm /path/to/apngasm` with an installed real 3.x. Tool is required only at APNG build time, not playback. `--per-action` can be omitted to export one loop per character. Files created: old `living_scene.gif`, `living_scene_assets.zip`, optional prior Godot/Blender packages, and new `living_scene_apng.zip`. The source ZIP additionally embeds the new APNG ZIP under `project/apng/`. No APNG is claimed if original art or executable is missing. License is preserved inside both ZIPs. Existing PixiJS / particles / tilemap / viewport pipeline remains available unchanged.
