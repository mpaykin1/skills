# BLOCKWILD v16 — Royal Volume Garden: source-authentic additions

## Goal

Improve the *existing* single-file BLOCKWILD v15 without replacing its embedded Unity-derived world archive, music, playable renderer, existing hero, or 160 eight-direction character pose sprites. New material on the walkable stone floor is sourced solely from owner-provided screenshot/reference with rights verified by the owner, not copied as an entire backdrop. The screenshot is an **art direction** reference, not the original Unity assets.

## Compatible authored skill pipeline

1. `blockwild-evolution` selects source-preserving improvement and verifies input SHA.
2. `godot-game-to-html` owns **true Unity original asset recovery** (UnityPy / AssetRipper / ILSpy where available). None of those external extraction binaries are included in this release or claimed to have run. Keep original Unity models distinct from author-made reconstruction.
3. `blender-model-animation-enhancer`, `voxel-game-creator` and `meta-game-fusion` exchange 3D static volumes through a canonical 48×48×64 palette occupancy grid; Sprite Stacking must always be physically coherent RGBA cross-sections, not a flat enlarged drawing. In this revision the implementation is all CPU NumPy/Pillow, with source-volume pre-baking and existing renderer.
4. `hero-animator` owns eight coherent views + five poses from prior v14/v15; **do not replace** the 160 existing user-selected hero/NPC PNG assets and source IDs.
5. `voxel-atmosphere-engine` and `game-style-forge` own subtle lantern illumination, world-space caustics, garden dust and shadows, sharing the existing RAF; no second gameplay state or renderer.
6. `blockwild-visual-benchmark` and `godot-game-to-html/browser-parity-capture` capture same-camera real Chromium frames, record measurable visual detail and palette metrics. No claim of subjective quality improvement from the score.

## Rebuild (owner-provided files required)

```
python skills/blockwild-evolution/scripts/build_v16_volume_props.py \
  --recipes skills/blockwild-evolution/scripts/build_sunlit_volume_sprites.py \
  --out build/bw16_assets.json
python skills/blockwild-evolution/scripts/make_stone_albedo.py \
  --reference-image REFERENCE_AUTHORIZED.jpg --out build/stone_albedo.png
python skills/blockwild-evolution/scripts/assemble_v16.py \
  --base-html BLOCKWILD_v15_SMOOTH_VOLUME_SUNLIT_GARDEN_OFFLINE.html \
  --assets-json build/bw16_assets.json --stone-texture build/stone_albedo.png \
  --out-html BLOCKWILD_v16_ROYAL_VOLUME_GARDEN_OFFLINE.html
```

All source-file inputs are immutable and the original game's embedded prefix is SHA-verified unchanged except for the page title. The extra stone image and 11 PNG assets are embedded into the final HTML as data URIs. Offline build-time uses Pillow + NumPy; source art/material extraction only with explicit rights. This exact supplied reference and v15 source reproduced the v16 final HTML byte-for-byte.

## Real rendered observations (2026-11-27)

- Full 53.7MB v16 HTML opened in Chromium with software 2.5D fallback; 189/189 RGB/RGBA alpha sprite atlases loaded; no JavaScript page errors.
- Portrait 390×844 and landscape 844×390 art render passed. Keyboard ArrowRight moved the single original hero from x31.5,z31.5 to x35.85,z27.19 in the original game runtime; source/fallback world toggle works.
- Original Unity 3D WebGL2 game engine not recovered or confirmed. Embedded original source world data (BWK1 and BWC1 compressed) still present in the HTML. At the observed full startup native source terrain/chunk ready flags were false, so do not claim full original world streaming verified.
- Matched full-canvas screenshot Laplacian variance (OpenCV) changed +37.81% portrait (818.77 → 1128.32) and +20.93% landscape (445.0 → 538.12), arithmetic mean +29.37%. **This is a high-frequency detail change, not a measured 29% improvement in artistic quality.** Floor-only ROI portrait +39.26%. No LPIPS pretrained weights available; do not invent LPIPS scores.

## Next strongest bottleneck

Recover genuine Unity Mesh/Texture2D and scene/material bindings from user-owned Windows ZIP using verified AssetRipper and/or UnityPy; then approved static GLBs → Blender CPU lighting/PBR bake → true sliced RGBA/texture atlas → existing renderer. Do not substitute RedLynx101/Blockwild for the supplied compiled game. Preserve game source rights and player identity.
