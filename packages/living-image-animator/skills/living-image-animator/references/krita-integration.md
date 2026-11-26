# Krita ↔ OpenToonz ↔ Pixelorama: original full-cel 2D/2.5D authoring

Upstream: https://github.com/KDE/krita (GPL-3.0-or-later; independent software; not bundled)
Official export: https://docs.krita.org/en/reference_manual/render_animation.html
Official import: https://docs.krita.org/en/reference_manual/import_animation.html

This is an executable **Krita PNG-sequence import bridge**, not a simulated Krita CLI exporter. Krita's supported Render Animation UI exports actual PNG image sequences; this plugin does not open `.kra` or generate cels itself. Keep original editable `.kra` as source and export full RGBA animation with **transparent background**, *exact actor canvas dimensions*, the requested FPS (24+), and **one numbered PNG per timeline frame**. Turn off visible paper/background layers. Export `Image Sequence` rather than MP4/GIF to preserve pixel registration and alpha. Manually draw complete separate full-character poses, not deformation of one still.

## Clip declaration

```json
{
 "action":"shoot",
 "krita_sequence":{
   "directory":"krita/archer/shoot_frames",
   "prefix":"frame_",
   "start_frame":0,
   "frame_count":24,
   "fps":24,
   "source_kra":"krita/archer/shoot.kra",
   "joints_json":"krita/archer/shoot.joints.json"
 },

}
```

`support_sequence` is required for a walking/running/stairs clip but **not** for ordinary gestures, shooting or falls; it must contain exactly one true foot contact state per exported frame. Characters' `joints_json` uses the exact same `frames` array and sprite-local root/two-joint positions as OpenToonz/Pixelorama. Each clip has >=12 frames and the final release gate still requires two independently active articulated actions per actor. No additional actor type exceptions for animals or horses.

PNG filenames are `prefix` + a decimal frame number + `.png`, e.g. `frame_0000.png` ... `frame_0023.png` (zero-based). The file reader checks consecutive numbers, duplicates, missing/extraneous frames, RGB/alpha, frame dimensions, original `.kra` format markers, landmark count, 1:1 frame-to-joint timing, frame rate, and ensures canvas pixels are unchanged in the cross-editor handoff. There is no alpha replacement, body warp, generated in-between, or implicit FPS conversion.

## Integrated pipeline

`unified_delivery.py` executes `krita_bridge.compile_scene()` first (Krita-registered images -> annotated `frames`), then the existing native OpenToonz `tcomposer` and Pixelorama `.pxo` cels, then the cross-editor handoff and strict full-pose GIF composer. Every `.kra`, user-rendered frame and joint file is preserved in ZIP `project/animation_sources/`. Krita source frames also generate two interoperable **importable assets** in `interchange_2d/`: an OpenToonz numbered RGBA image level (`opentoonz_levels/<actor>/<clip>/...0001.png`) and a Pixelorama-importable row-major RGBA spritesheet (`pixelorama_import/<actor>/<clip>.png`). `krita_handoff.json` describes frame order, dimensions, counts and source project SHA. Existing `.tnz` ↔ `.pxo` exchange remains intact.

Use the same command:

```bash
python scripts/unified_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24
```

Add `--opentoonz /path/to/tcomposer` only if there are native `.tnz` clips, and `--pixelorama /path/to/Pixelorama` only for native `.pxo`. No Krita executable is needed to *ingest a PNG sequence*, but **Krita must have been used to draw/export the sequence**. This pipeline does not create an editable `.kra`, `.pxo` or `.tnz` automatically; source projects remain separate from PNG/spritesheet interchange. An artistic review at playback size remains necessary to prove animation quality.
