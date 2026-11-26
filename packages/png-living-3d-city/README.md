# PNG → Living 3D City

Open a transparent PNG or a crop from a white architectural atlas, preserve the painting as facade texture, and export a true-depth GLB for Three.js/Blender. `examples/` contains textured 3D buildings, bridge and floating island extracted from the four reference images supplied for this request. See `skills/png-living-3d-city/SKILL.md` for the complete workflow.

These are **first-pass relief models**, not perfect 360° reconstructions and not a hosted game. The packed city GLB is an arranged static geometry example; a living interactive city needs Three.js streaming, authored effects and approved animations as described in the skill.


## v1.2 — architectural underside completion

Default `png_to_glb.py` outputs include a source-textured 3D finish instead of a horizontal cut. Options: `--foundation auto|rock|arches|masonry|fragments|mist|none`. `finish_edges.py` generates physical foundations/arches/rock/debris; `runtime/foundation_effects.mjs` adds independent, smooth in-game GLSL fog, drifting shards, and cyan energy. The three new open-source libraries (CSG, Quarks, coherent noise) are optional; not preinstalled by this archive.


## v1.3 — actual rendering library integration layer

Pinned npm dependencies: Three.js 0.185.0, three-mesh-bvh 0.9.18, three-bvh-csg 0.0.18, three.quarks 0.17.1, quarks.core 0.17.1, postprocessing 6.39.6. See `skills/png-living-3d-city/runtime/package.json` and `runtime/install_runtime.py`. `advanced_effects.mjs` contains real import-based CSG/Quarks/Postprocessing implementation. Dependency bytes require a successful network-enabled install; fallback GLSL and geometry remain independently runnable.


## v1.4 — user uploaded 3 libraries (vendored source)

From the provided ZIPs: `three-bvh-csg@0.0.18`, `three.quarks@0.18.0` + `quarks.core@0.18.0`, and `postprocessing@6.39.6` are physically copied under `skills/png-living-3d-city/runtime/vendor` with original license files. Quarks is additionally transpiled from TS to ESM JS. `node runtime/verify-vendor.mjs` checks the offline source layer. Full bundling requires separate `three`, `three-mesh-bvh`, and `esbuild` packages; these were not in the supplied ZIPs and npm registry was unavailable in this environment. Do not mark a game bundle ready until those dependencies resolve.

## v1.5 — visible effects or no release

Code existence is not visual proof. A new hard gate checks the actual exported HTML with a deterministic close-up camera and pixel-differential screenshots for all five base styles in both desktop/portrait and orbit views, including motion and runtime exceptions. See `references/visible-effects-release-gate.md` and `scripts/visible_effects_gate.py`. Nocturne II's black screen and weak/invisible foundation styles are explicitly blocked by this gate.
