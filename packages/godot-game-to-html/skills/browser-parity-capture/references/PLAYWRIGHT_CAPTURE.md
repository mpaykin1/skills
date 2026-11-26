# Playwright capture module — sources and boundary

- Upstream Microsoft Playwright: https://github.com/microsoft/playwright (Apache-2.0); pinned Python version: `1.65.1`.
- Official screenshot API: https://playwright.dev/docs/screenshots
- Official Python API: https://playwright.dev/python/docs/screenshots
- Existing sibling Pixelmatch guard: `skills/visual-parity-guard/scripts/visual_parity.py`, Mapbox `pixelmatch@8.0.0` ISC.

Input can be original browser URL (`http(s)`), exported `index.html` directory or standalone `.html`. Original and derivative must be visualized in the same browser, camera position, viewport, FOV, source time/state, exposure. Local export uses loopback HTTP and standard MIME types for Godot/Unity. The capture does not mutate either source. One identical scenario is replayed separately for original and candidate. Outputs are matched screenshot directories; existing Pixelmatch compares them with configurable threshold and a hard gate.

Dynamic procedural effects require game-specific deterministic capture hooks implemented inside an explicitly authorized *copy* of each game; this tool does not invent parity under unsynchronized snow/fog. Browser render differences across GPUs/OS may also affect Pixelmatch, so comparison on the same browser/host is preferred. No web rendering or real full-game fidelity can be guaranteed from schema validation alone. Screenshots are intermediates, not final game deliverables.
