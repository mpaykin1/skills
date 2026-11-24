# Visible effects and no-cropped-bottom mandatory release gate (v1.5)

Trigger: Every authored PNG→3D building/city and every update to an HTML preview or game. This gate takes priority over labels such as "integrated", "implemented", "running", "finished" or screenshots of a different build.

**A feature only counts when it exists in the actual delivered file, is visibly rendered at the intended default camera, is distinct and readable, and stays correct during camera motion.** Source code, comments, manifests, bundled packages and invisible geometry do not qualify. A generated HTML must either demonstrate this or explicitly state that a feature is missing.

## Architecture finishing, non-negotiable

1. Classify each building bottom: `masonry`, `rock`, `mist`, `arches`, `fragments`, or intentional combined modes. Keep an inventory and a shared anchor for the genuine PNG facade and the lowest *visible* opaque pixels. Reject mismatched y-coordinates and unmapped UVs.
2. Place finishing geometry in the **same building transform and local coordinates** as its original facade, with actual shared seam overlap and coherent stone texture. The top of finishing geometry must intersect the opaque facade by 2–5% of its visible height. No piece may merely float behind or below a straight, uncovered alpha boundary.
3. Each style requires a **recognizable silhouette**: masonry has corbels/columns/cornice; rock tapers irregularly with non-coplanar 3D sides; mist has physically diminishing solid base AND luminous, translucent, drifting volume; arches have true negative space, columns and gothic spandrels; fragments have individually moving rocks with meaningful travel radius and no avatar deformation. Fog alone must never conceal a raw crop. Preserve art source style.
4. Place a near-camera reference building before finalising the default camera. The facade and its entire finishing transition must both fit in the first visible frame; base must be visibly distinguishable from dark sky and foreground. On the first playable screen, show at least 3 different finishing types; all five types must be recognizable during a short, accessible flight route without editor/debug controls.
5. Preserve full appearance in 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315° camera orbit plus top-down. A beautiful front is insufficient if a side reveals crop, floating polygon or untextured back.
6. Mist particles must have perceptible motion and size; crystal glow must not blow out the original PNG. Fragments must move independently, not pulse by scaling the same still. Small, low-opacity dots do not substitute for visible debris.
7. **Fallback parity:** WebGL and Canvas2D fallbacks must share the same 5-effect identity and visible finished bases. A WebGL runtime exception must be surfaced, not silently passed as a successful advanced renderer. Falling back cannot drop required effects. `window.onerror` recovery alone is not adequate release verification.
8. Libraries `three-bvh-csg`, `three.quarks`, `postprocessing` count as **active in the delivered HTML** only if their exact code is actually imported/bundled, executed and observable. "CSG-style", "Quarks-style" and "PMNDRS-inspired" procedural alternatives count as *custom approximations*, not actual use of the libraries. Bundling vendor source inside the plugin does not automatically activate it in game HTML.

## Required reproducible visual inspection interface

Each delivered game HTML must support local-only deterministic URL parameters (no network or debug UI required):

- `pngcity_audit=1`: enter inspection mode using identical camera, light, seed, frame time and geometry across comparisons.
- `effect=masonry|rock|mist|arches|fragments` chooses a reference building that displays that effect prominently. It must zoom/orbit so the **base** occupies a substantial central portion of the viewport.
- `enabled=1|0` toggles ONLY the chosen foundation effect; all other scene content is identical.
- `yaw=0|90|180` fixes camera orientation relative to the reference building; `time=2.0` fixes animation frame.
- Expose `window.__PNG_CITY_VISIBILITY__` with `{ready: true, effect: <name>, enabled: boolean, renderer: "webgl2" | "canvas2d", activeVendorEffects: { csg: boolean, quarks: boolean, postprocessing: boolean }, error: null}`. Do **not** mark true merely because vendor files exist. The `ready` flag means the effect and assets have finished loading and the requested frame has actually drawn.

The gate script `scripts/visible_effects_gate.py` takes the exact shipped HTML and opens it through `file://`. It compares real image pixels for each effect against its effect-disabled control with identical camera/time, tests yaw=0 and 90, desktop 1280×720 and portrait 390×844, and checks runtime errors and canvas content. If the HTML does not implement the inspection interface, release is **not verified**; do not bypass by calling the script optional.

Example:

```bash
python skills/png-living-3d-city/scripts/visible_effects_gate.py ./NOCTURNE.html --output ./review-frames
```

The script is intentionally strict: at least 1% of the **central 75% of the frame** must materially change when an effect is enabled, and at least 70 pixels must show visible local difference. An effect must also survive the 90° orbit. For animated mist/fragments capture another deterministic `time` and check perceptible movement **inside the effect region**. A successful image difference alone does not certify artistic coherence; inspect composite images for raw straight cuts, visible seams, overlap, silhouette continuity and source identity. If there is no Playwright/browser, mark verification blocked and do not claim PASS.

## Delivery contract

- No "all effects implemented" claim solely from code or a screenshot showing just fog and a distant skyline.
- Show the **actual** exported default desktop and portrait frames with near-camera foundation, and one close-up 90° orbit with original facade and base both in frame. All effects must be obviously readable at gameplay scale.
- Reject if any browser exception, black screen, unresolved external URL/CDN (when offline requested), invisible base, raw PNG crop, wrong building transform or fallback downgrade.
- If validation cannot run, deliver work as incomplete preview with explicit limitations. Never report visual quality percentages from code review alone.
