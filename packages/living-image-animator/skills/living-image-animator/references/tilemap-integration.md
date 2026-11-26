# @pixi/tilemap 5.0.2 — authentic Tiled tile layers with original 2D/2.5D cels

Official source: https://github.com/pixijs-userland/tilemap , MIT. Compatible with PixiJS >=8.5.0. Official `CompositeTilemap` batches many tiles with original source texture pixel data. All tile images remain exactly as exported by the artist; no 3D mesh, geometric replacement of character poses, or fake animation. Browser bundle is installed from genuine npm package `@pixi/tilemap@5.0.2` by `scripts/tilemap_vendor.py`. Plugin doesn't ship the binary; if the network or npm fails, use a genuine local browser bundle `--tilemap-js`, never CDN in offline HTML.

## Actual interoperability

`scripts/tilemap_delivery.py` calls `pixi_particles_delivery.py` first. Full original full-body PNG frames, pose gate, original GIF/ZIP, Tiled/LDtk navigation geometry, Godot, Blender, PixiJS A*, pixi-viewport, Filters and real v8 particles all remain mandatory and untouched. Matter.js physics remains an additional distinct browser output and is not falsely claimed in this tilemap view. The new HTML player is additive and fully offline with all its actual JS dependencies inlined.

The tilemap layer data comes **only** from `project/tiled/original_map.json` written by original `tiled_bridge.py` and compared byte-for-byte with the author's original Tiled JSON. The original scene must include `scene.tiled.map_json`, and existing registered Tiled map canvas size must match the approved PNG. For each Tiled `tilelayer` (finite, orthogonal, uncompressed integer array), the bridge loads each source-authored image tileset PNG relative to the original map file, validates dimensions, firstgids and sheet bounds, embeds it losslessly, and draws genuine GIDs as `CompositeTilemap.tile(texture, x, y, {u,v,tileWidth,tileHeight})`. Source sheet hashes are retained and original PNGs are included under `project/tilemap/` inside assets ZIP. Up to 180k explicit tiles. Rendering is batched in 4096-cell segments and added to the **existing** PixiJS world/camera; source actor atlases, transparent cels, physical paths, UVs and drawn anatomy are never changed.

For transparency and exactness, current bridge intentionally rejects compressed/infinite maps, external TSX, animated or flipped GIDs, isometric maps, offsets and tile sources without authentic originals. The existing LDtk stage continues to provide authentic walkable/blocked geometry, NPC paths and flat image layers; this new rendering adapter currently renders Tiled `tilelayer` cells, not LDtk autoLayer tile grids. Never claim LDtk tile art has been batch rendered unless a separate source-verified adapter exists. The original full-scene background remains; tile layers are additive transparent authored tilemaps, not guessed substitutes for its drawing.

## Author settings

Optional `scene.pixi.tilemap`:

```json
{"enabled":true,"layer_z":{"Ground":-90,"HighDeck":90}}
```

The source `.json` Tiled map must have a `tiled` configuration already accepted by the original pipeline, with authentic tile layers, the atlas PNGs, and source-aligned geometry. Default layer depth is `-50 + original_layer_order` (behind the actors). Explicit `layer_z` uses existing tilelayer names. No tile-based activity counts toward genuine character motion.

## Output

```bash
python scripts/tilemap_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24 \
 --fetch-pixi --fetch-viewport --fetch-filters --fetch-particles --fetch-tilemap
```

Prior editors/models are external prerequisites only if used by their corresponding original clips. With genuine locally downloaded runtimes pass `--pixi-js`, `--viewport-js`, `--filters-js`, `--particles-js`, `--tilemap-js` (and `--pathfinding-js` if needed). Missing tools/source art means explicit failure, not fabricated output. New `living_scene_pixi_tilemap.html` and `living_scene_pixi_tilemap.zip` are standalone offline scene artifacts only after all previous original quality gates pass; they are not a public website or a published game.
