# PixiJS Filters 6.1.5 × PixiJS 8 × pixi-viewport 7.0.3

Official MIT upstream: https://github.com/pixijs/filters (PixiJS v8 requires pixi-filters v6); actual version inspected: 6.1.5. No 3D avatars or body deformations. No CDN dependencies in generated HTML.

## Working integration

`pixi_filters_delivery.py` first runs the **original** `pixi_viewport_delivery.py` -> `pixijs_atlas_delivery.py` -> `pixijs_delivery.py` -> Blender/Godot/LDtk/Tiled -> SAM 2 / MMPose / DeepLabCut / ControlNet Aux / Krita / OpenToonz / Pixelorama -> strict full-cel pose/GIF/ZIP validators. It **never** substitutes FX for frame-authored character movement. The post-stage `pixi_filters_bridge.py` validates original `living_scene_assets.zip`, consumes the same approved 2.5D level planes, and patches only the additional autonomous `living_scene_pixi_filters.html`. Original GIF, approved sprite PNG/atlases, PixiJS, A*, Matter.js, camera and other browser builds remain unchanged.

The official compiled JS is required: `pixi_filters_vendor.py` downloads authentic `pixi-filters@6.1.5` using npm, verifies package name/version, PixiJS v8 peer, MIT LICENSE, and extracts `dist/browser/pixi-filters.min.js`. Pass `--filters-js /path/to/pixi-filters.min.js` if already installed. Network is required only for initial vendoring. No fabricated JS or streaming CDN. If the package's dist layout changes or is unavailable, this stage fails; fix official package retrieval, never replace the engine with a mock.

**Effects are applied ONLY to full-canvas background and original registered 2.5D environment planes.** Animated character sprites, atlas UV rectangles, independent full-pose PNGs, actor `z`, world coordinates, FPS, identity locks, contact and pose gates are unchanged. Glow/bloom may be used on original isolated lamp/window PNG layers, blur on an artist-supplied translucent haze plate; they cannot automatically invent fog, lighting layers or missing artwork. The source `.png` layer must already be registered in scene `godot.layers`/`blender.layers` (including source-defined Tiled/LDtk contributions). Max 16 selectively filtered layers, bounds on filter strength/blur radius/quality to limit GPU cost. Brightness/contrast/saturation apply to *background only*.

## Author settings in scene.json

```json
{
  "pixi": {
    "filters": {
      "enabled": true,
      "background": {"type":"adjustment","brightness":0.91,"contrast":1.1,"saturation":0.84},
      "planes": [
        {"png":"planes/train_windows.png","type":"glow","distance":3,"outerStrength":1.2,"color":"#efaf65"},
        {"png":"planes/mist.png","type":"blur","strength":1.2,"quality":2},
        {"png":"planes/moonlight.png","type":"bloom","threshold":0.7,"bloomScale":0.75,"blur":2}
      ]
    }
  }
}
```

This is illustrative: `planes/...` PNGs must actually be present, authored, alpha-transparent, and registered with accurate source size. Without explicit settings, the **extra FX-only HTML** uses subtle default background-only contrast/saturation/brightness, leaving all existing HTML outputs untouched. Use `"enabled":false` to disable effects. Individual layer options are validated; any unknown type or unregistered art fails rather than silently applying a visual substitute.

## Build

```bash
python scripts/pixi_filters_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --fetch-pixi --fetch-viewport --fetch-filters
```

For fully offline building supply genuine local browser assets `--pixi-js`, `--viewport-js`, `--filters-js` and optionally `--pathfinding-js`; existing `--opentoonz`, `--pixelorama`, etc., are forwarded. The final ZIP adds `project/browser/living_scene_pixi_filters.zip` with the self-contained HTML and MIT LICENSE, without changing already approved source assets. This is a visual browser playback renderer; it does not claim the Matter.js physics artifact is embedded into the FX viewport variant. Actual browser/WebGL execution is necessary to verify visible effects on a user's scene. It cannot make new animated character poses from a still, and cannot produce a hosted game URL without deployment.
