---
name: sprite-sheet-helper-bridge
description: >
  Official Kyonru Sprite Sheet Helper headless CLI (MIT, pinned Git SHA) converts real approved Godot/Unity GLBs or real sprite-stacked source into multi-angle PNG atlases and Godot/Unity/Phaser exports without inventing character animation. Interoperates with earlier danielwh2 four views, sprite-in-the-round, Grunge stack.json and Three.js/PixiJS.
---
# Sprite Sheet Helper — original-art, multi-angle atlas bridge

Use the actual upstream `Kyonru/sprite-sheet-helper` CLI, MIT license, pinned commit `aacb362aa35e4fec8102f7d08e9955d65c03eb88` (v0.8.3 at inspected revision). Do not replace it with a home-grown perspective image generator. Source: https://github.com/Kyonru/sprite-sheet-helper.

The adapter `scripts/export_atlas.py` exports **real original model renders** from GLBs. For an approved META GAMES `stack.json`, the existing `sprite-in-the-round` bridge exports a palette-textured GLB from **the same actual horizontal RGBA slices**, then this official CLI captures 8 directions into a transparent atlas. For a four-view PNG, the previous danielwh2 carver creates real volume first. The original PNG/GLB and game engine source remain untouched. This is a derivative atlas, not a playable game conversion or recovered GDScript/C#.

```bash
# Original animated Unity/Godot GLB: use original animation tracks (never synthesize missing frames)
python skills/sprite-sheet-helper-bridge/scripts/export_atlas.py /approved/hero.glb --out /output/hero-atlas --workflow three-quarter-8dir --format spritesheet --frames 8

# Existing approved source-authentic PNG volume -> previous sprite-in-the-round GLB -> 8-direction atlas
python skills/sprite-sheet-helper-bridge/scripts/export_atlas.py /approved/stack.json --out /output/stack-atlas --format godot

# Source artwork with four authored TOP/SIDE/FRONT/BACK views -> previous first OSS carver -> atlas
python skills/sprite-sheet-helper-bridge/scripts/export_atlas.py /approved/four-views.png --four-views --out /output/four-view-atlas --packed
```

The normal main-skill entry is `skills/godot-game-to-html/scripts/sprite_sheet_atlas.py` with identical options.

**Actual chain:** original GLB animation or verified PNG stack → existing four-view/round bridge as needed → upstream CLI with `--workflow three-quarter-8dir --fit auto --fitScope all` → real rendered PNG atlas and JSON metadata. Use optional `--normal-map` for aligned normal atlases and `--packed` for generic compact spritesheet, or `--format godot|unity|phaser|zip|gif` for that upstream format. `--frames` is sample count per source clip; it does not produce authored animation where no clip exists. Use manual authored full-volume poses for character movement and preserve stable hero ID/pivot across shots.

First invocation installs and builds the **exact pinned official Git commit** using git, npm, Node, then Puppeteer opens a local Chromium browser. This stage needs available Chromium and any Linux graphics libraries; if missing, install Chromium through the Puppeteer version bundled with the cached upstream (`npx puppeteer browsers install chrome`). For offline use, pass `--no-install-helper --helper-root /trusted/built/repo` and `--no-install-upstream` for previous stacks. No unaudited CDN script or upstream executable is embedded in a game HTML. Previous browser Playwright/Pixelmatch must compare representative renders to the original before promotion. Original native Godot/Unity WebGL remains the only full gameplay implementation.

**Provenance:** source SHA-256, upstream commit, selected workflow and original intermediate GLB are retained with the generated atlas. The emitter refuses to overwrite existing results, fails on unavailable source tools rather than drawing procedural substitutions, and checks real exported PNG files. An animated character with only a static PNG stack must NOT be labelled as a recovered animated hero. Source code/asset rights are required.
