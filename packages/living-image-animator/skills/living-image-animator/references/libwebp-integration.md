# Real libwebp animation × authentic APNG/GIF/Godot/Blender (v0.30)

Upstream: https://github.com/webmproject/libwebp — original `COPYING` 3-clause BSD-style copyright license. Official tool: https://developers.google.com/speed/webp/docs/img2webp . This plugin does not bundle the libwebp C source or binary; the real open-source libwebp codec is called via the separately installed Pillow C extension **or** an optional official `img2webp` binary. The default Pillow backend is actual native libwebp, **not** a mock encoder. It runs entirely on CPU; no GPU, npm, WebGL, online API or API key is needed to build lossless WebP once Pillow with WebP support is installed.

## How the OSS integrations reinforce one another

1. First run the **unchanged** Krita/OpenToonz/Pixelorama → SAM2/MMPose/DeepLabCut/ControlNet Aux references → full-pose gait/identity validations → original GIF+ZIP → Godot/Blender pipeline. WebP cannot bypass a single original actor action, anatomical or visual-continuity requirement.
2. `scripts/libwebp_bridge.py` calls the **existing** `pixijs_bridge.load_scene()` and original `motion_gate.json.all_actors_pass`; reads only source PNG bytes at `project/inputs/...`, **never** the color-reduced GIF or synthesized images. Encodes `lossless=True`, full RGBA alpha, no color palette, no morphs or source-frame alterations. The Pillow C bindings invoke genuine installed `libwebp` animation encoder/decoder. The alternate `--img2webp` mode invokes official installed `img2webp -lossless -exact -m 6 -loop 0`, with per-frame millisecond durations.
3. 24fps => duration timestamps spread with a bounded integer-millisecond error (e.g. 42/41ms); never declare perfect sub-millisecond timings in a format that stores integer ms. The decoder verifies the precise total runtime, visible source pixel values (RGBA) and alpha against every **source frame temporal midpoint**, allowing only lossless coalescing of adjacent identical poses. Any deviation aborts export.
4. `scripts/libwebp_delivery.py` invokes **the full unchanged `blender_delivery.py`** first. `--with-apng` instead invokes the existing **`apngasm_delivery.py`** first, giving actual both-format results for every identical source actor. The additional `preferred_animated_assets.json` uses real final byte sizes to select the smaller WebP or APNG asset per action; it does not claim that WebP must always compress better. The original GIF, APNG (if requested), full source PNG ZIP, Godot/Blender outputs and all PixiJS/PathFinding/Matter/filters/particles/tilemap modules remain intact.
5. WebP and APNG are directly usable in browser `<img>` and data URIs. The WebP export is an **asset pack**, not a claim of an interactive HTML game, A* movement, physical collisions or a hosted URL. Those remain in their existing independently exported HTML engines. A playback image does not compute correct world path: the author must use the original actor root paths in PixiJS or Godot for world locomotion.

## Commands

CPU-only WebP export without APNG executable:

```bash
python scripts/libwebp_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --per-action
```

Both genuine animation formats from the exact same source art:

```bash
python scripts/libwebp_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --per-action --with-apng --apngasm /path/to/apngasm
```

Or use `--with-apng --build-apngasm` with actual C++/CMake/git dependencies/network; or supply `--img2webp /path/to/img2webp` to use the official compiled libwebp CLI rather than Pillow. `--preflight-only` forwards the complete original scene gate and does not produce/certify final animation assets. Real Pillow with libwebp support is the default native encoder, installed with standard Pillow package and libwebp libraries.

Output new `living_scene_webp.zip` with transparent `actors/<id>/complete_cycle.webp` plus optional individual `<action>.webp`, `manifest.json`, `preferred_animated_assets.json`, original `LICENSE.libwebp.txt`. Package also appears inside the already-approved `living_scene_assets.zip` under `project/webp/`. No existing original asset is deleted, modified or replaced.

## Limitations

- **Lossless ≠ all the originally invisible RGB bytes**: alpha=0 pixel RGB may be discarded by codecs; all **visible** RGB and every alpha value are checked pixel-perfectly. Nonzero alpha color is never approximated. Real authored pose joints/frame cadence unchanged.
- A decoded WebP encoder may legally coalesce identical adjacent input frames; compare images at their actual source time, not encoded frame index. Excessive WebP memory limits or browser animation performance are device dependent; no FPS/small-size claim without actual files and playback verification.
- A 40–60s GIF is still validated before WebP, and WebP actor cycles are short loops from the original validated complete action sequence. The new file itself does not replace full scene GIF duration.
