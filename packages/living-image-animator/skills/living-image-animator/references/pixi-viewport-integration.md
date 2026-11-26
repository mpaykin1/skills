# Pixi-viewport v7.0.3 × PixiJS v8 — true 2D/2.5D camera

Official source: https://github.com/pixijs-userland/pixi-viewport ; MIT; latest researched version v7.0.3 (Nov 2026), peer dependency PixiJS >=8. Real browser UMD is `dist/pixi_viewport.umd.cjs` and MUST load after PixiJS v8.7+; do not generate a fake replacement, use a CDN, or substitute an external host when autonomous HTML was requested. Project source, frames, shaders and scene metadata preserve their original licenses.

## Architecture

- Keep **all** original cast-wide PNG pose-quality, action timing, contact, no-warp, identity and loop guards intact. No stage bypass: `pixi_viewport_delivery.py` executes `pixijs_atlas_delivery.py` -> prior PixiJS/PathFinding.js -> Blender -> Godot -> Tiled/LDtk -> SAM2/MMPose/DLC/Krita/OpenToonz/Pixelorama -> full-cel GIF/ZIP validation. Only after the original accepted `living_scene_pixi_atlas.html` exists does it add a viewport variant.
- `pixi_viewport_bridge.py` injects the real browser UMD into a **new** self-contained `living_scene_pixi_viewport.html`, rather than overwriting the already approved original atlas HTML. It replaces the PixiJS root world Container with the upstream `pixi_viewport.Viewport` container.
- Camera: original `renderer.events`, touch drag, pinch, wheel, inertial deceleration, scale clamping and underflow centering. The actual mouse/touch input is delivered to PixiJS, not simulated in Python. Dynamic camera pan affects background/foreground layers; each original authored parallax factor adjusts relative to the camera's position. Full-character pixels, sprite UVs, source PNGs and animation FPS remain unchanged.
- Optional follow target follows only one known, stable original actor ID. No auto-guess, no substitute character, no body-part transformation. Optional keyboard camera pan is opt-in. All existing PathFinding.js navigation, Tiled/LDtk annotation, weather and Godot physics implementations remain preserved *in their existing artifacts*; the viewport variant itself is a camera-driven replay of approved PNG animation, not a game with A* collisions.
- Browser output: `living_scene_pixi_viewport.html` single-file + `living_scene_pixi_viewport.zip` + included in `living_scene_assets.zip`. The original GIF, atlas HTML and all previous artifacts survive unchanged. Runtime verification in an actual browser is needed before claiming gameplay-quality camera controls.

## Authoring options

In the original `scene.json`, use:

```json
"pixi": {
  "weather": "snow",
  "parallax": {"planes/horizon.png": 0.3, "planes/foreground.png": 1.3},
  "viewport": {
    "min_zoom": 0.7,
    "max_zoom": 3.5,
    "drag": true,
    "pinch": true,
    "wheel": true,
    "keyboard": false,
    "follow_actor": null
  }
}
```

`min_zoom`/`max_zoom` are relative to initial fit-to-screen scale, must surround 1, and keep within allowed .2–8. `follow_actor` must reference exactly one existing, approved cast ID. Camera movement is a view transformation only; **do not** count camera movement, stage parallax, weather or UI as character animation. With `weather_screen_space=true`, snow/rain are composed on the screen and remain independent of the moving camera.

## Runtime setup

```bash
python scripts/pixi_viewport_vendor.py --out vendor/pixi_viewport.umd.cjs
python scripts/pixi_viewport_delivery.py source.png --scene scene.json --out output \
  --seconds 48 --fps 24 --fetch-pixi --viewport-js vendor/pixi_viewport.umd.cjs
```

Or `--fetch-viewport` to download exact `pixi-viewport@7.0.3` through `npm pack`. `PIXI_VIEWPORT_BUNDLE` resolves a manually preinstalled genuine UMD. Runtime builds require npm/network **only once** for vendoring; existing genuine local engine files can create standalone HTML completely offline. External PixiJS v8 and pixi-viewport binaries are NOT included in the plugin skill, and a missing binary is a hard error, never a silent fallback. Stage produces an HTML player; creating a PUBLIC URL requires actual hosting.
