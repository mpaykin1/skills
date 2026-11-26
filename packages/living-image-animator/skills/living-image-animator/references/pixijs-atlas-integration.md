# PixiJS 8.23.0 atlas performance upgrade — additive to existing genuine OFFLINE HTML

**Upstream:** https://github.com/pixijs/pixijs (MIT license); official PixiJS 8 texture-framing guide: https://pixijs.com/8.x/guides/components/textures . The existing living-image-animator `pixijs_bridge.py`, `pixijs_delivery.py` and `pixijs_vendor.py` are preserved byte-for-byte. This release does NOT replace the earlier offline single-file HTML or its original release gates.

## Real composition

- `pixijs_atlas_delivery.py` invokes the existing `pixijs_delivery.py` **first**. This already requires authentic SAM2 / MMPose / DeepLabCut references where present, hand-painted Krita / OpenToonz / Pixelorama cels, complete `pose_sequence_delivery.py` cast validation, 24fps+ 40-60s GIF/ZIP, Tiled/LDtk world, Godot/Blender source creation and genuine pinned PixiJS 8.23.0 UMD bundle. If upstream fails, no optimized output is created.
- `pixijs_atlas_bridge.py` then invokes the same existing `pixijs_bridge.load_scene()` and `bundle_path()` security/identity/zip validators. Only *already accepted* original full-frame RGBA art is unpacked from original individual PNGs and packed losslessly into GPU-friendly at-most-4096px texture atlas pages. Each alpha/RGB cel is compared pixel-for-pixel against the source immediately after packing. PNG decoding/packing never warps, rotates, scales or synthesizes character pixels. Multiple original actions and phase offsets are retained. Frames are selected by integer `Math.floor(elapsed*fps)`; actor movement follows original `locomotion.path` using the same smoothstep world placement, not changing the sprite image.
- `pixi_runtime.js` runs real PixiJS 8 `Application`, `ImageSource`, `Texture({source,frame:Rectangle})`, `Sprite`, and WebGL. It builds four depth layers: registered original background, optional original alpha architectural depth planes, source-painted animated characters, and optional weather particles. `scene.pixi.parallax` defines camera-only movement of user-authored original depth planes and is NOT evidence of locomotion. `scene.pixi.weather` can be `"snow"`, `"rain"` or null. If neither is supplied, no weather is invented.
- `living_scene_pixi_atlas.html` remains **fully offline**, because the *same real pinned PixiJS UMD build* is embedded inline (downloaded by existing `pixijs_vendor.py` via `--fetch-pixi` or supplied via `--pixi-js`). There is **no CDN fallback**. If source, engine, identity or release gate is unavailable, fail explicitly. The original `living_scene_pixi.html` is retained alongside the optimized one.
- Archive `living_scene_pixi_atlas.zip` contains the offline HTML. It is additionally embedded under `project/browser/` in the existing original `living_scene_assets.zip`. Original character frames, GIF, Godot/Blender source and previous PixiJS HTML are not overwritten or changed.

## Command

```bash
python scripts/pixijs_atlas_delivery.py source.png --scene scene.json --out output \
  --seconds 48 --fps 24 --fetch-pixi
```

Or provide local genuine `--pixi-js /path/to/pixi.min.js`, or `PIXIJS_BUNDLE` environment variable. Existing `--pixelorama`, `--opentoonz`, `--mmpose-device`, `--comfyui-url`, `--godot`, `--blender` optional flags are forwarded to original pipeline. For 2D/2.5D no 3D character model is necessary or acceptable as a substitute. Browser game publishing still requires explicit hosting; a generated local HTML file is not a public website.

## Optional scene properties

```json
"pixi": {"weather":"snow", "parallax": {"layers/back_forest.png":0.35,"layers/foreground.png":1.2}}
```

Original `godot.layers`/`blender.layers` already define which scene-painted PNG depth planes exist. The maps use those exact original relative PNG paths. Unknown parallax fields simply do not create new art. Weather is atmospheric only, never evidence of motion of a horse/human.

**Limitations:** no new character frame generation, no guarantee of perfect artistic quality, no 3D physics, no re-use of missing character back/front art, no invented animation. Running PixiJS in a real browser depends on a WebGL-capable device; local software verification cannot certify user-device FPS.
