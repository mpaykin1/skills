# Real upstream `danielwh2/sprite-stacking` — v0.38 direct bridge

Official upstream: https://github.com/danielwh2/sprite-stacking — MIT copyright © 2026 Daniel White.

**Unlike the prior attribution-only reference**, the new `danielwh2_vendor.py` verifies the actual official source code by original Git object SHA1, and `danielwh2_delivery.py` literally launches the upstream `views_to_slices.py` CLI. It creates actual four-view visual-hull carved PNG slices, original preview HTML and check sheet, and a strict original source pixel retaining `stack.json` adapter. Full source + 360 preview can then be rendered by existing true volumetric Three.js/GLSL, when a real Three.js ESM is locally supplied. This is an additive *artifact preparation* path, not a replacement for the existing full scene or any character motion gate.

The repo's `README.md` explicitly describes the order TOP/SIDE/FRONT/BACK, a **horizontal left-to-right ground-to-roof slice strip**, options `--slices`, `--order`, `--colours`, `--shade`, `--dark-thresh`, `--preview`, `--html`, and the original interactive standalone viewer. We supply `--order reading`, `--colours 0`, `--shade 0`, `--dark-thresh 0` to avoid optional color quantization, shading and contour stripping. The original source still performs its genuine geometric intersection and silhouette calculation. For artist-painted Grunge Horror, its pixel-art biased reconstruction should be considered a candidate, not exact recovered 3D truth. Distinct slices, RGBA fidelity to the original output strip, canonical pivot, no fake copied layers, and actual license are required.

Source pin (`Git blob SHA1`, not a version tag):
- `skills/sprite-stacking/scripts/views_to_slices.py`: `73972c1019988dcdb119bc8d9ba0ad55c0fcfd2d`
- `skills/sprite-stacking/scripts/viewer.html`: `429e4b9cbd4413c586c3621ef7db694bbc514ab7`
- `skills/sprite-stacking/SKILL.md`: `fd9288455c3e2681816ddf86eaaeed3186e27f25`
- `LICENSE`: `f94c9b150dc7e0cbfcdf9f9d8bcff4aa79ca5688`

**No original upstream binaries, untrusted web scripts, or placeholder views ship inside this overlay.** Genuine source is fetched from official GitHub once, then cached and integrity-verified. When network is blocked and no genuine local checkout exists, return a clear dependency error instead of claiming the upstream ran. All existing sprite stack, YUKA, Matter, Pixelorama, Krita, OpenToonz, Godot, Blender, FFmpeg, Rhubarb and Howler components remain intact. Previous source-authored `stack.json` usage is unchanged.
