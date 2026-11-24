# Production: animated 2D/2.5D scene, strict full-cel pipeline

1. From original artwork/video, inventory every visible human, animal and horse by immutable ID, including background and window figures. Register source pixel coordinates, exact masks, clean background and four scene strata. Plan distinct active actions per actor.
2. Draw independent full-character key poses, breakdowns and in-betweens at 24fps+ with consistent anatomy and identity. Do NOT deform still images, rotate extracted limb cutouts, interpolate art with optical flow or substitute environment movement for character animation.
3. Use Krita GUI **File > Render Animation > Image Sequence** to export exact RGBA PNG frames and keep its `.kra`. Or use original native `.tnz` with `tcomposer` / `.pxo` Pixelorama CLI. Annotate each cel with actual root + two visible joints, and each locomoting cel with contact support. Source artwork must be present; bridge cannot hallucinate poses.
4. Describe action clips as `krita_sequence`, `opentoonz_scene`, `pixelorama_project` or `frames`. Compile with `scripts/unified_delivery.py`. Krita is the first stage, native OpenToonz the second, Pixelorama the third, then original PNG cross-editor handoff; no static shortcuts.
5. Human MMPose reference tracks are optional measured guides; horse and cat art must be separately drawn. World-space trajectory, foot contact, cycle closure and per-actor pose coverage are mandatory for actual walking/running.
6. Strict final compositor uses only original full-cel pixels, separately moving scene depth and atmosphere. Validate actual actions at playback scale; publish GIF+ZIP only if all actors pass. ZIP contains source `.kra/.tnz/.pxo`, masks, all original poses, frame indices and importer-friendly cross-tool spritesheets/numbered levels.

```bash
python scripts/unified_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24
```

Add `--opentoonz` and `--pixelorama` only when native `.tnz` and `.pxo` are in the scene. Full engine dependencies and Krita GUI are external; this plugin includes file adapters, validators and the compositor, not installed artist programs or magic scene authoring.
