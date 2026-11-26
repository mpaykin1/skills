# PixiJS 8 GPU Particle Emitter: original source-locked environment

Source: https://github.com/spd789562/pixi-v8-particle-emitter . License: MIT. Pinned npm `@spd789562/particle-emitter@1.0.2`, designed specifically for PixiJS v8 `ParticleContainer`. Bundled editor/engine runtime is **not** embedded in this plugin archive; source adapter and verified pinned builder are included.

## Combined pipeline

`scripts/particle_emitter_delivery.py` runs the full existing `pixi_filters_delivery.py` pipeline first: authentic original actor cels -> full-cel 24fps+ source-validation GIF/ZIP -> Tiled/LDtk map -> Godot/Blender -> genuine PixiJS+PathFinding.js -> atlas -> pixi-viewport -> real PixiJS Filters. It then adds an entirely new `living_scene_pixi_particles.html` containing a **real** pinned particle-emitter browser IIFE, no CDN, no fake Canvas particle figures, keeping all actor sprites, original IDs, frames, paths and camera logic unchanged. Particle emitters are separate atmospheric nodes and may run behind or in front of actors by their author-specified z-order. Existing `Matter.js` physics artifact is preserved as separate output; do not pretend the viewport player contains collision physics. PixiJS Filters still apply only to background and original painted scenery plates; do not attach effects to the actor atlases.

## Engine build and interoperability

The upstream npm library is ESM/CJS with `pixi.js` imports. `scripts/particle_emitter_vendor.py` installs exact original `@spd789562/particle-emitter@1.0.2` and `esbuild@0.25.12` in an isolated temporary folder, validates original manifest/MIT license, and builds a browser IIFE. Its Pixi adapter exports bindings from the **single real pinned `window.PIXI` engine** that is already part of this offline HTML, avoiding incompatible duplicate copies of PixiJS. The built global is `window.LIA_ParticleEmitter.Emitter`. All environment models and npm runtime files remain external until actually installed. If npm/network is absent, builder fails unless provided genuine prebuilt `--particles-js`. This cannot silently fall back to CDN.

## Scene authoring

```json
{
  "pixi": {
    "particles": [
      {"id":"snow_in_courtyard","type":"snow","region":[0,0,720,400],"density":110,"speed":24,"z_index":90},
      {"id":"chimney_embers","type":"embers","region":[380,150,80,70],"density":35,"speed":36,"z_index":65,"tint":"#ed8b32"}
    ]
  }
}
```

Supported ambient presets: `snow`, `rain`, `embers`, `dust`. Each system has a stable non-character ID, an explicitly authored `region=[x,y,w,h]` in original source pixels, bounded particle `density` <=300 and total <=900, optional drift `angle`, bounded `speed`, `tint`, `scale`, and depth `z_index`. No actor is ever rebuilt from particles. The original source scene must separately contain **complete drawn** full-pose cels and all real gait metadata. Visual particles do **not** count towards character motion. Atmosphere is not a physical weather interaction solver; rain, smoke and snow do not change collision/contact or original root positions.

## Command

```bash
python scripts/particle_emitter_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --fetch-pixi --fetch-viewport --fetch-filters --fetch-particles
```

Additional external flags for installed native sources/models (`--pixelorama`, `--opentoonz`, `--godot`, `--blender`, `--mmpose-device`, `--comfyui-url`, `--pathfinding-js` or `--fetch-pathfinding`) are forwarded. To build offline with no npm: provide **real local** `--pixi-js`, `--viewport-js`, `--filters-js` and `--particles-js` binaries. Do not use insecure online imports in output HTML. The new `living_scene_pixi_particles.zip` includes the standalone HTML and the real MIT license; it is also placed under `project/browser/` inside the existing assets ZIP, leaving all existing artifacts untouched. A playable hosted URL requires a separate actual publish step.
