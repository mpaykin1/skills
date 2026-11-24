---
name: png-living-3d-city
description: Convert user-authored PNG or white-background JPEG architectural atlases into genuine volumetric textured GLB facades and procedurally assembled living 3D cities. Original painting on every front; no replacement with primitive shapes. Supports floating Gothic sky cities, bridges, infinite flying and atmospheric Three.js/GLSL render plans.
---

# PNG LIVING 3D CITY — 1.5.0

## When to invoke
A user supplies a painted PNG/JPEG of a building, facade, bridge, floating island, or sheet of such assets, and wants a 3D game, 3D model, or city that visually preserves the painting. The result must contain **real mesh depth**, **original PNG material** and **animated environments** (when a world/game is requested). Free, commercially compatible tools preferred.

## Non-negotiables
1. Original user art is the visual authority. Do not replace the drawing with default boxes, flat-generated buildings, stock textures, a painting-like synthesis, or new unrelated designs.
2. Do not pass off a single sprite billboard as an all-angle 3D object. Each model must have volumetric silhouette sides, depth and side-wall geometry. Meaningful 3D features (window recesses, buttresses, cornices, columns, protruding balconies) should be individually modeled when viewpoints make them visible.
3. Preserve alpha: white-background JPEG atlases are not transparent PNGs; extract **separate** assets, remove white including holes in bridges, decontaminate fringes; don't claim alpha exists before processing. For complex transparent ornaments use SAM2, then manually inspect masks.
4. ORIGINAL PNG → COMPLETE PNG VIEW SET (MANDATORY): the input may show only the front. The skill MUST automatically create separate user-inspectable PNG views for FRONT, LEFT, RIGHT, REAR and ROOF from the source painting, reusing its brushwork, colors, architectural motifs and true cutouts. Use inferred artistic generation where the source lacks physical information; never falsely claim the source contains those hidden views. Prefer extra user-painted views if supplied; otherwise create compatible new PNG artwork. Face textures must be UV mapped onto *real volumetric geometry*; reject blank flat sides, tint-only materials, mirrored front used as final back, stretched windows, billboards and generic voxel boxes. At ±45°, ±90°, 135°, 180° and elevated viewpoints the same architectural identity and major landmarks remain recognizable. No delivery with untextured sides or reverse.
4a. Included `png_to_glb.py` now emits original front and distinct source-derived `*_left.png`, `*_right.png`, `*_back.png`, `*_roof.png` with UV-mapped materials. This is a first-pass visual approximation; production-quality all-angle PNGs and actual roof/side depth should be painted/refined with a dedicated texture-generation pass before all-angle acceptance.
5. Front retains UV-mapped original PNG. Side/rear/roof surfaces MUST carry distinct stylized PNG images and 3D trim. Deliver every side view as a separate PNG; if a generation pass is incomplete, mark the result incomplete rather than substituting default materials.
6. When requested as a game: all NPCs/hero sprites must be genuine approved animation cycles, never animated by stretching/distorting one still; hero actions strictly from input. Full portrait and landscape mobile support. Keep every scene alive through independently animated environmental elements.
7. `file://` autonomous HTML means bundling local Three.js/GLSL code and every asset; CDN references disqualify an autonomous claim. Only claim a working hosted game after actual publishing.
8. Renderer and geometry occupy separate contracts: GLB conversion via this skill, interactive city via meta-game-fusion / game-style-forge / hero-animator; do not claim these are automatically installed or interconnected merely because they are referenced.
9. Respect licenses of every model checkpoint and image. In particular, only Depth Anything V2 Small is freely Apache-2.0 licensed; Base/Large/Giant checkpoints are CC BY-NC 4.0. `rembg`'s MIT does not grant commercial rights to all of its optional weights.

## MANDATORY: NO ABRUPT LOWER PNG EDGE — five-stage architectural finishing

The Nocturne vertical-sky-city preview exposed lower PNG facades with straight horizontal crops, breaking the illusion of architecture. **Never ship a bare horizontal building edge.** All new and existing PNG->3D scenes must deliberately finish each base in the SAME original artwork style; foreground and close viewpoints are the strictest. A complete 360° textured building must also have a complete lower silhouette.

The skill now includes `scripts/finish_edges.py`, invoked by `scripts/png_to_glb.py` (default `--foundation auto`). Its geometry embeds new user-source-derived stone textures into GLB and emits `*.foundation.json`. Choose a foundation style per building: `masonry` (extended walls, cornices); `rock` (inverted suspended stone island with irregular taper); `arches` (parametric true-depth open arcades and columns); `fragments` (source-derived 3D rock chips, independently animatable); `mist` (short physical tapered base plus moving blue haze and fragments). Composite them by depth: close = detailed architecture + islands, middle = arches + debris, far = mist + light.

**All five effects** must remain available and actively composable across a city. For all-angle architecture do not stretch the user facade to cover missing stone, insert monochrome quads, mirror the front to the rear, or hide a hard cut with a flat strip. Adapt the feature to building type and original PNG cues. Failure to close the bottom silhouette means an incomplete preview. `runtime/foundation_effects.mjs` provides smooth independently animated GLSL mist, a blue energy shaft and floating-shard motion to add to the real 3D GLB geometry. It does NOT embed the Three.js engine; bundle it locally for offline autonomous games.

Full technical spec, commands and optional OSS integrations: `references/foundation-completion.md`.

## The strong hybrid — visual 3D architecture

### Real spatial layers
- **Depth**: 3D silhouettes in at least 3 z-layers, occlusion, volumetric fog and genuine parallax; distant skyline is low-contrast blue and nearby towers have texture detail.
- **Body**: high/low polygon architectural volumetric mesh, silhouette extrusion, front façade UV, physical-side buttresses, recessed arches, balcony slabs and rooftop spires. Don't use a billboard alone.
- **Illustrated facade**: preserve exact PNG front colors and ornaments, including hand-painted windows, subtle texture and watercolor edges.
- **Relief and light**: independent shallow 3D layers for window glass, columns, doorways and portals; PBR/emissive window inserts, screen-space contact shadows, bloom only on light sources.
- **Living weather**: depth-aware animated particle rain, mist sheets, cloud volumes, lamp shimmer, slow world-time light; floating islands independently drift, bridge-lamps glow, energy rings turn.
- **Screen**: ACES tone mapping, carefully bounded bloom, subtle chromatic aberration/grain, scalable DRS / LOD as needed.

### Infinite sky-city
- Fixed random seed per city chunk (x,y,z) to avoid pop-in or changing buildings while revisiting.
- Pool/reuse geometry and materials; swap chunks outside the frustum; origin rebasing for unlimited travel distance.
- `EXT_mesh_gpu_instancing` or Three.js InstancedMesh for repeated trim/details; don't instance unique silhouettes if it destroys variety.
- Flight: arrows/WASD and touch joystick (x/y), ascent/descent (keys or touch buttons); render at 100dvh, both phone orientations; camera smooth follow without involuntary hero gestures.

## Pipeline
1. Classify source: standalone RGBA or white-matted atlas. Identify every object separately, including tower, bridge, floating island, windows, balconies, hero sprites, sky, effects.
2. Extract each using original color. For white JPEG with simple negative space, use local OpenCV segmentation with background unmatting; for complex openings SAM2 + edge cleanup. Keep approved silhouettes.
3. Create first-pass real 3D GLB using bundled `scripts/png_to_glb.py`. This produces front/back UV planes, volumetric wall geometry along exterior and opening contours, and the transparent original art file. **It is a first-pass relief, not a reconstructed all-angle castle.**
4. For production, augment the GLB with modeled window recesses and depth: build roof, side walls, towers and bridges in Blender Geometry Nodes or CSG; apply authored side textures/material atlases and genuine emissive surfaces. Compare with references at 0°, ±45°, 90° and top-down.
5. Generate a city with `scripts/city_builder.py` or assemble in the game engine using instancing and chunk streaming. The included builder produces an **arranged static GLB sample**, not a complete infinite game.
6. In Three.js add gameplay, audio, real animations, GLSL fog/weather, optimized GPU instances; ensure the image identity remains recognizable, then publish only on request.

## Working commands

From the skill root directory's parent, with dependencies available:

```bash
python -m pip install pillow numpy opencv-python-headless trimesh
python skills/png-living-3d-city/scripts/png_to_glb.py facades.png out/tower.glb --height 24 --depth 4 --foundation arches
python skills/png-living-3d-city/scripts/png_to_glb.py atlas.jpg out/bridge.glb --bbox 0 420 350 610 --white-bg --height 8 --depth 3 --foundation rock
python skills/png-living-3d-city/scripts/city_builder.py out out/city.glb --cols 8 --rows 3
```

`city_builder.py` expects exactly `tower.glb`, `bridge.glb`, `island.glb` in its input directory; it writes a combined GLB and a position manifest JSON. Segment all assets separately before combining. Named geometry must be preserved (`original_png_front`, `real_silhouette_depth`).

## Component integration (contracts, not installed integrations)
- **SAM2** optional mask refinement for architecture openings and overlapping cutouts.
- **rembg** optional generic automatic background removal, checking model weight licenses separately.
- **Depth Anything V2 Small** optional per-pixel depth hint for facade relief; depth estimate is relative, not a certified mesh.
- **Blender Geometry Nodes** builds buttresses/arched corridors/side walls/roofs and exports PBR GLB.
- **Three.js** renderer, transforms, instancing, camera, input and GLSL postfx.
- **three-mesh-bvh** precise collisions and facade raycasts for player/scene.
- **glTF-Transform and meshoptimizer** optimize output GLB, atlas textures and GPU instances.
- **meta-game-fusion** game world and animation guard; **Hero Animator** approved character cycles; **Skill Nexus** optional orchestrator.

## License references
Project links and licensing caveats are in `references/opensource.md`; review upstream at integration time. This skill does not vendor third-party checkpoints, codebases, or noncommercial models.

## Mandatory view continuity rule, inherited by all PNG-aware game skills
When making architecture from PNG for any moving camera, always construct and preserve an explicit `views` manifest with `front.png`, `left.png`, `right.png`, `rear.png`, `roof.png`, their provenance (`source`, `inferred` or `artist-approved`), UV mapping and shared identity anchors. Both left/right MUST be independently coherent; no blind flip as final output. Preserve proportion, unique window, clock, dome, spire and arch motifs across orbit and top-down views. For small decorative 2D sprites this rule only applies if converted into volumetric architecture, not to independent character animation.


## Optional rendering engine packages — pinned integration (v1.3)

**Mandatory installation gate:** For each 3D-world task requiring open CSG archways, Quarks magical debris/particle emitter, or PMNDRS bloom, run `python skills/png-living-3d-city/runtime/install_runtime.py` on a network-enabled builder. It installs the real `three-bvh-csg`, `three.quarks`, `postprocessing` alongside their compatible `three`, `three-mesh-bvh` and `quarks.core` versions, and bundles the integration module. Use `runtime/advanced_effects.mjs` exports rather than replacing them with fake, same-named functions. `npm run verify` must show all resolved. Detailed integration in `references/npm-integrations.md`.

USER ZIPs NOW PHYSICALLY VENDORED inside `runtime/vendor/` (CSG 0.0.18, Quarks 0.18.0 + its core, postprocessing 6.39.6; with licenses and compiled Quarks JS). These exact source packages are installed in the skill release. Runtime Three.js 0.187.0, three-mesh-bvh and esbuild are not provided by the ZIPs; full runtime build requires these dependencies and a successful `npm install`. Until then use the built-in `foundation_effects.mjs` fallback and do not claim active bundled effects. In final offline HTML, embed the actual JS and avoid all external imports. Consult `references/npm-integrations.md`.

## v1.4 — offline user-supplied vendor layer

The user-supplied ZIPs are unpacked in `runtime/vendor/`; this is real copied source code, not a list of URLs. Verify with `node runtime/verify-vendor.mjs`. Quarks 0.18.0 TypeScript is transpiled to JS and linked with its 0.18.0 core. Run `runtime/install_runtime.py` only where the remaining Three.js and build dependencies can be resolved. Keep finished architecture and approved PNG materials unchanged.

## ABSOLUTE RELEASE BLOCKER — VISIBLE FINISHING (v1.5)

Read `references/visible-effects-release-gate.md` BEFORE assembling a city or completing any PNG architecture. Every final HTML MUST actually show the intended foundation types at gameplay scale; code and meshes by themselves are insufficient. Use the exact emitted file, deterministic audit URL controls and `scripts/visible_effects_gate.py` to compare screenshots with on/off effects in near-camera views at desktop, portrait and yaw=0/90. FAIL CLOSED: no viewport screenshots, no verified pixels, no completed release. Camera default must show close-up buildings including their bases, not solely atmospheric distant skyline. A fallback renderer is a distinct build and cannot silently downgrade features.

**Library honesty:** Having vendored `three-bvh-csg`, `three.quarks`, `postprocessing` in the skill does not mean any particular exported offline HTML includes or runs them. Confirm actual imports and execution in the delivered game. CSG-style meshes, Quarks-style particles, and inspired custom GLSL postfx count as different implementations, not installed library usage in that HTML. Never claim they are active unless actually bundled and visibly running.

**High priority bug prevention:** Do not reference undeclared variables inside any generated scene loop. Run browser execution on the finished exported file and record pageerrors. Never substitute a merely nonblack frame check for evidence that the five finishing effects are visible and correct. At least three distinct finishing types must be obvious in the first scene; all five in accessible flight path. Review the raw lower alpha silhouette of every foreground asset at 0/90/180 degrees.
