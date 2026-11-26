# Native PixiJS 8 CullerPlugin × Tiled GPU tilemap × pixi-viewport

Official MIT code: https://github.com/pixijs/pixijs/blob/dev/src/culling/CullerPlugin.ts and https://github.com/pixijs/pixijs/blob/dev/src/culling/Culler.ts. Official performance guidance: https://github.com/pixijs/pixijs/blob/dev/skills/pixijs/references/performance.md . Version: **PixiJS 8.23.0**, already pinned by the existing PixiJS vendor. The separate `pixi-cull@2.1.0` **is not used**: its declared PixiJS peer range covers v6/v7, not v8. This new integration is native to PixiJS 8 and does not require an extra npm package or a duplicated renderer.

`pixi_culling_delivery.py` invokes the already implemented `tilemap_delivery.py`, which itself runs the full original source PNG identity/motion/GIF/ZIP checks, real source Tiled/LDtk, Godot/Blender, PixiJS A*, camera, filters, particles and actual `@pixi/tilemap` map GPU generation. A new additional standalone `living_scene_pixi_culled.html` and corresponding ZIP are made only after an approved original `living_scene_pixi_tilemap.html` exists. All existing outputs, including the distinct interactive Matter.js physics HTML, remain untouched.

`pixi_culling_bridge.py` reads the `scene.json`, approved `motion_gate.json` and exact original Tiled `project/tiled/original_map.json`, validates the orthogonal grid and chunks the **already-approved same tile cells** by their source grid position. Every chunk is a genuine `CompositeTilemap` with exact original tileset/UV/XY/alpha/z-order; `mesh.cullArea` holds its original pixel bounds, `mesh.cullable=true`, `mesh.cullableChildren=false`.

Before `PIXI.Application.init`, register `PIXI.extensions.add(PIXI.CullerPlugin)` from the **already embedded actual PixiJS v8.23.0 runtime**; initialize with `{culler:{updateTransform:true}}` to avoid last-frame camera transform lag on fast moves. PixiJS checks the screen against each chunk's transformed bounds before rendering. Character display objects are never marked for culling and their original 24+ FPS full-frame animation / logic continues regardless of camera visibility. Effects, physics and original artist files are never altered. Environmental particle emitters remain independent; culling is strictly for Tiled GPU tile chunks. This improves rendering when many map chunks are offscreen; FPS gain depends on scene and device and must not be invented.

Optional original scene settings:

```json
"pixi": {
  "culling": {"enabled": true, "chunk_tiles": 32}
}
```

`chunk_tiles` is 16–64; max 4096 spatial chunks, to avoid too many draw calls on sparse maps. Unsupported Tiled source maps still fail under prior strict gate; no procedural replacement, arbitrary screen crop, or regenerated tile graphics. When no Tiled map is supplied, use the original PixiJS entrypoints without this additional stage.

```bash
python scripts/pixi_culling_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --fetch-pixi --fetch-viewport --fetch-filters \
  --fetch-particles --fetch-tilemap
```

All native executable and approved pose requirements are inherited. `--pixi-js`, `--viewport-js`, `--filters-js`, `--particles-js`, `--tilemap-js` may point to actual preinstalled local binaries; no CDN or mock culling. Full original GIF plus transparent asset ZIP stay mandatory. Browser-level gameplay/visual proof requires running the generated HTML in a browser; packaging alone is not proof of FPS gains.
