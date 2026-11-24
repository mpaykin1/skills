---
name: browser-parity-capture
description: >
  Microsoft Playwright Chromium (Apache-2.0) automatically captures real Godot/Unity native Web and Three.js/PixiJS HTML frames, replays the same controls, then sends matched PNGs to existing Pixelmatch 8.0 + glTF Validator fidelity gates. Original games unchanged, no synthetic scene.
---

# Microsoft Playwright — original vs optimized WebGL real-frame capture

**New component: [Microsoft Playwright](https://github.com/microsoft/playwright), Python `playwright==1.65.1` (Apache-2.0).** Install separately with `python -m pip install playwright==1.65.1` and `python -m playwright install chromium`. No browser or binary is vendored in the plugin. This module runs only at build-time and requires a real browser. Its capture code is `scripts/capture_and_compare.py`.

## Usage

```bash
python skills/browser-parity-capture/scripts/capture_and_compare.py --original /build/original/web --candidate /build/optimized/web --out /captures/compare-001
python skills/browser-parity-capture/scripts/capture_and_compare.py --original https://original.example/game/ --candidate /build/optimized/game.html --out /captures/compare-002 --scenario /approved/same-actions.json
```

Optional scenario JSON (same actions on both sides, screenshots named identically):

```json
{"steps":[{"action":"screenshot","name":"00-start"},{"action":"press","key":"f"},{"action":"hold","key":"w","ms":850},{"action":"wait","ms":300},{"action":"screenshot","name":"01-lamp-and-walk"}]}
```

The script opens the **original exported game** and the **candidate exported game**, with identical browser engine, viewport, DPR, ready selector and input sequence. Local HTML/Web export folders are served temporarily over `127.0.0.1` HTTP with COOP/COEP headers appropriate to many Godot/Unity builds. Screenshot files go only into a fresh separate folder; game sources are read-only. Then the **existing** `skills/visual-parity-guard/scripts/visual_parity.py` invokes Mapbox Pixelmatch. Any failed frame blocks the candidate. `--browser-executable /trusted/path/to/chromium` supports an existing official system browser if the pinned Playwright browser is absent. `--capture-only` is explicit and makes **no claim** about similarity; `--no-install` prevents Pixelmatch npm installation. Real WebGL screenshots, no emulated Canvas or invented source graphics.

## Cooperation and limits

- Godot Engine/Unity Editor builds are authoritative gameplay. Playwright captures them; it does **not** convert game logic or replace shaders.
- UnityGLTF / Three.js / PixiJS derivatives can be captured with the same settings; glTF Validator ensures structural validity while Pixelmatch checks aligned rendered images. xatlas/Blender/OIDN/OpenImageIO/KTX2/glTF-Transform can contribute candidates only after source assets are preserved.
- Randomized snow, procedural fog, physics, real-time particles, variable frame timings, asynchronous loading, cameras, differences in original/candidate controls or mismatched browser GPU all make results inconclusive until scene and camera state are synchronized. Playwright does **not** freeze game time, seed RNG, disable shaders, or alter original gameplay automatically. For «ЛЕЕР», visual parity cannot be reported as % of the whole game based on a few frames.
- Browser screenshots may show loading screens instead of actual gameplay if only a generic `canvas` selector is awaited. Supply a stronger `--ready-selector` and scenario for the game. Always visually inspect real frames. Pixelmatch thresholds measure aligned pixels only, not complete-game fidelity or semantic correctness.
- This does not introduce new runtime dependencies into exported HTML, and does not install browser binaries without an explicit installation command. No scripts are injected into the target game.
