# pixi-v8-particles × PixiJS 8 × pixi-viewport × pixi-filters

Open-source runtime: https://github.com/VasKostadinov/pixi-v8-particles (MIT, v0.1.3; adaptation from pixijs-userland/particle-emitter, both attribution lines retained). **Not** the incompatible pre-v8 `@pixi/particle-emitter` package; library's `peerDependencies` explicitly require PixiJS `^8.0.0`.

## Additive composition

`pixi_particles_delivery.py` first invokes the *entire* existing `pixi_filters_delivery.py` with unchanged options: independently painted frame validation, original GIF/ZIP, Godot, Blender, Tiled/LDtk, PixiJS source animations, source atlas, pixi-viewport camera and source-only pixi-filters. Only after successful upstream rendering does `pixi_particles_bridge.py` augment a **new** offline `living_scene_pixi_particles.html` with genuine `Emitter`/`registerAllBehaviors`, preserving every original character texture, motion gate, world path and PNG hash. This particles output is an atmospheric viewport player. Matter.js collision and A* gameplay remain in their **separate** existing browser artifacts; do not claim physics is newly integrated into this effects-only HTML.

The library is loaded after the real PixiJS UMD runtime and prior effects scripts, with the original PixiJS global shared via esbuild's Pixi shim. No second Pixi installation is embedded into the output HTML. Exports include `Emitter` and `registerAllBehaviors`; pre-existing untouched original character cels are never selected as particle textures. `pixi_particles_vendor.py` checks genuine pinned `pixi-v8-particles@0.1.3` and builds browser IIFE with esbuild `0.25.12`, mapping `pixi.js` imports to the HTML's existing `window.PIXI`.

## Original scene.json options

```json
{
  "pixi": {
    "weather": "snow",
    "emitters": [
      {"id":"snowstorm","kind":"snow","space":"world","position":[0,0],"zone":[0,-10,960,20],"rate":42,"max_particles":350,"speed":95,"lifetime":7,"size":1.6,"z":9000},
      {"id":"train_smoke","kind":"smoke","position":[380,205],"zone":[-10,-10,20,20],"rate":18,"max_particles":120,"color":"#92949a","z":15},
      {"id":"sparks","kind":"sparks","position":[500,300],"rate":16,"max_particles":80,"z":70}
    ]
  }
}
```

`zone` and `position` use original source-canvas coordinates; adapt to source size. Allowed `kind`: `snow`, `rain`, `smoke`, `embers`, `sparks`, `dust`. `space` is `world` or `screen`; optional `attach_actor` must resolve an already accepted real cast ID and requires `world`, for dust tracked to feet. `particle_png` optionally references an existing original author-supplied registered environmental PNG in `project/inputs/...`, *never* an actor's full-body pose. Omitted `pixi.emitters` + source `pixi.weather=snow|rain` automatically replaces the previous procedural weather with real particles rather than doubling snowfall. No weather declared -> no artificial effect is invented.

Budget: max 12 emitters, 350 particles each, 1200 particles total, bounded lifetimes, rates, size, zone and color. No remote images, no shaders or physics on actors. Sparks and embers can borrow **existing** pixi-filters GlowFilter on their environmental holder only, not on character art. All emitter textures originate from `PIXI.Texture.WHITE` or original approved environmental PNGs. Motion is simulated in real `Emitter.update(deltaSec)` and tied to existing viewport world/screen coordinates. All original hand-drawn actors continue on their own authentic authored flipbooks.

## Offline build

```bash
python scripts/pixi_particles_delivery.py source.png --scene scene.json --out output --fps 24 --seconds 48 \
  --fetch-pixi --fetch-viewport --fetch-filters --fetch-particles
```

If the current source has a real navigation actor, also include `--fetch-pathfinding`. Optional `--particles-js /path/to/genuine/pixi-v8-particles.iife.js` avoids network if prebuilt with `pixi_particles_vendor.py`, or set `LIA_PIXI_PARTICLES_BUNDLE`. Existing `--pixi-js`, `--viewport-js`, `--filters-js`, `--pathfinding-js` and native editor/model flags pass through unchanged. npm, package weights and engine binaries are **not** silently claimed installed. If missing, block final build without substituting custom faux-particle animations or CDN scripts. A hosted game URL requires a separate actual deployment.

**Critical:** dynamic smoke, rain, snow and postprocessing never qualify as character motion. Do not skip any visible rider, horse, person, shopkeeper, window occupant, original sprite frame, gait contact, original GIF or alpha sprite ZIP. Native engine visual playback verification is required before claiming visible FX on a published site.
