---
name: pixi-original-sprites
description: >
  Converts original 2D and 2.5D sprites and full independent image-frame animations extracted by UnityPy or recovered from Godot/Unity projects into a single autonomous PixiJS 8.23.0 HTML. Preserves original frames and alpha; never substitutes generated geometry or claims to recover C#/GDScript gameplay.
---

# PixiJS original 2D sprite bridge — Godot / Unity → Autonomous HTML

Use for **authorized original** image assets (`PNG`, `WebP`, `JPG`) from Godot/GDRETools or Unity/AssetRipper/UnityPy. Keep the original WebGL export as the actual playable game. PixiJS is a complementary 2D/2.5D visualization runtime; Three.js is the complementary 3D GLB runtime. **Neither viewer alone reconstructs game mechanics.**

## Actual toolchain

`UnityPy PNG sprites / Godot original PNG frames → author-supplied layout JSON → PixiJS v8.23.0 → embedded JS + data-URI assets → single offline HTML`

The packer is `scripts/pixi_sprites_to_html.py`. It uses the official pinned NPM `pixi.js@8.23.0` browser bundle (`dist/pixi.min.js`) and automatically installs that package to a versioned local cache if missing. Its output has **no runtime CDN**. For a network-free build, supply `--pixi-js /path/to/pixi.min.js --no-install` or a preinstalled cache. The package is MIT; acknowledge PixiJS contributors. **Do not** bundle random remote JavaScript or claim offline support when the bundle isn't present.

### One-command visual output

```sh
python skills/pixi-original-sprites/scripts/pixi_sprites_to_html.py /assets/my-scene.json --out /output/my-scene.html
```

An actual `my-scene.json` declares original frame files **relative to its own directory**, coordinates, depth/layer, alpha, and animation FPS. User-authored complete frames only: no deformation, tweening poses into different characters, fake sprites or reduced-amplitude replacement animations.

```json
{
  "title":"Original 2D world","width":1280,"height":720,"background":"#08121b",
  "pixelArt":true,
  "sprites":[
    {"name":"sky","file":"assets/sky.png","layer":"background","x":640,"y":360,"anchor":[0.5,0.5],"parallax":0},
    {"name":"hero","frames":["assets/hero_run_0.png","assets/hero_run_1.png"],"fps":12,"loop":true,"x":520,"y":480,"layer":"midground"},
    {"name":"fog","frames":["assets/fog_0.png","assets/fog_1.png"],"fps":8,"alpha":0.4,"layer":"foreground","x":640,"y":360,"parallax":16}
  ]
}
```

The scene supports `background` → `midground` → `foreground` → `screen`, explicit z-index, parallax tied to pointer, independent frames/FPS, transparency, pixel-art nearest filtering, touch/mouse handling and responsive letterboxing. It never mutates original images. Sprite transforms and parallax are visual **presentation**, not restored gameplay logic.

### Direct UnityPy synergy

```sh
python skills/pixi-original-sprites/scripts/pixi_sprites_to_html.py /recovered/unitypy_manifest.json --out /output/original-sprite-catalog.html
```

`unitypy_manifest.json` comes from `godot-game-to-html/scripts/unitypy_extract.py`. The adapter reads `Sprite` and `Texture2D` items and produces a paginated **source sprite catalog**, not an invented Unity scene. UnityPy's `path_id`, file provenance and original images are not modified. To achieve the original world composition instead of a gallery, use verified Unity/AssetRipper scene coordinates in an explicit scene JSON.

### Common entrypoint

```sh
python skills/godot-game-to-html/scripts/universal_game_to_html.py /recovered/unitypy_manifest.json --out /output/sprites --mode sprites
```

Output is `out/sprites.html`. Direct original Unity/Godot projects still use `--mode web` for native WebGL. GLB scenes still use the Three.js bridge. This prevents alternate renderers from replacing the same game.

## Limits and safeguards

- Requires real decoded PNG/JPG/WebP image files and local PixiJS browser bundle at **build** time. Node/npm network is optional only if library installation is needed; **offline at runtime**.
- All resources embedded as base64; output can be large. `--max-mb 256` (adjustable), 500 sprites/240 frames per sprite max; a UnityPy catalog displays 30 entries per page.
- A UnityPy catalog is neither a playable game nor a reconstruction of original layout. Independent original frame assets preserve character identity; nothing is animated unless several real source frames are provided.
- Missing original animations, input behavior, C#/IL2CPP or GDScript cannot be filled in by PixiJS itself. Build original WebGL first when source exists; keep shaders, camera, UI, sound and mechanics authoritative in Godot/Unity.
- `--force` is required to overwrite an existing output. The packer refuses absolute/remote asset URLs, escaping symlinks and missing inputs.
- Run resulting HTML in a browser before claiming `file://` compatibility of a particular device; provide a real playable link only after a real game is deployed.
