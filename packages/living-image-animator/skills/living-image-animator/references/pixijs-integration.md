# PixiJS v8 × Living Image Animator — autonomous HTML runtime

Upstream open-source project: https://github.com/pixijs/pixijs , official v8 API: https://pixijs.com/8.x/guides/components/application . MIT license: https://github.com/pixijs/pixijs/blob/dev/LICENSE . Pinned distribution version: **8.23.0**.

## Actual integration

- New Python `scripts/pixijs_bridge.py` reads **only** a previously completed, zipped, authenticated independent pose scene after `motion_gate.json.all_actors_pass == true` and v3 `full-frame-pose-sprites` scene schema.
- It embeds **the true published PixiJS v8 browser bundle** (`pixi.min.js`) and original, full-sprite PNG bytes as inline data in one `living_scene_pixi.html`. The HTML needs no CDN, web requests or external files and can open directly in a browser, provided the actual engine bundle is available when BUILDING.
- PixiJS `Application` hosts independent frame-sequence `Sprite`s for every actor with original `phase_frames`, one 24+fps timeline, original source-space `(x,y)` path keys and smoothstep position interpolation; **no deforming** character pixels, bone transforms, part rotation, resynthesized poses or optical-flow frames. Sprite graphics are nearest-neighbor, scene-scale responsive, and screen layers use the source-registered PNG plates already collected by Tiled / LDtk / Godot / Blender. The image sequence's image identity is checked by the original compositor first.
- HTML is generated as a **third/fifth actual artifact after** GIF, sources ZIP, Godot ZIP, Blender ZIP. `scripts/pixijs_delivery.py` invokes `scripts/blender_delivery.py`, so no older release gate, original editor or scene-motion validator can be bypassed. The resulting `living_scene_pixi.html` is also inserted in the source ZIP at `project/browser/`.
- PixiJS is **not a replacement** for Godot physics: it replays the original authored 2D/2.5D world path and animation frames. Interactive navigation with `NavigationAgent2D`/physics, A* obstacle avoidance, stairs semantics and in-scene NPC choices still belong to the Godot project. Do not claim the browser HTML implements runtime collision or interactive gameplay when it does not. Clicking canvas pauses/resumes animation only.

## Genuine dependency installation

The PixiJS binary is NOT compiled from thin air and must never be fabricated. The included `scripts/pixijs_vendor.py` runs pinned `npm pack pixi.js@8.23.0 --ignore-scripts`, checks package and MIT LICENSE metadata and extracts its real browser distribution. It requires working npm and internet access. It does not require a GPU for building; displaying uses browser WebGL.

```bash
python scripts/pixijs_vendor.py --out vendor/pixi.min.js
python scripts/pixijs_delivery.py source.png --scene scene.json --out output \
  --seconds 48 --fps 24 --pixi-js vendor/pixi.min.js
```

Or pass `--fetch-pixi` to the final command to automatically run the npm downloader before rendering, or set `PIXIJS_BUNDLE` to an already downloaded genuine PixiJS v8 bundle. If npm, network, original pose artwork, certified GIF/ZIP, PixiJS binary or source-relative PNGs are unavailable: **fail visibly**, never silently generate CDN-dependent/non-Pixi substitute output. `--preflight-only` retains upstream validation only and does not certify the standalone HTML.

MIT attribution is embedded inside the HTML. Do not strip license notices when distributing. Browser HTML supports offline playback, not remote deployment or publicly hosted URL: publishing a link requires separate explicit hosting. No claim of actual PixiJS runtime playback unless opened in a real browser and verified.

## Scene compatibility

Original scenes can include `scene.tiled` or `scene.ldtk`; those adapters enrich the verified `scene.json` with `godot.layers`, `blender.layers` and geometry metadata. PixiJS renders the original PNG depth planes and source-relative whole actor trajectories, **never invents frame-based art**, **never reclassifies actors or changes their roles**, and does not substitute programmatic shapes for approved characters. Four visual strata remain source-derived.
