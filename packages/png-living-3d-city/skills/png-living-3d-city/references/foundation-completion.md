# No-hard-cut architectural completion — mandatory

**Trigger:** any PNG/JPEG painted building, tower, island or bridge whose lower silhouette ends unnaturally in midair in an interactive Three.js/GLSL scene. The original painted front remains authoritative. Build the new missing portion underneath: never simply apply a horizontal crop mask, rectangle or billboard to hide the gap.

## Five composable effects

1. **Architecture extension (`masonry`)**: source-derived stone PNG + physical 3D stepped cornices, masonry continuation, buttresses, arched arcade. Detect repeated horizontal bottom-edge pixels with original alpha silhouette, use masonry trim to cover join. NO hard termination of the new continuation; couple it to the next option.
2. **Floating inverted rock (`rock`)**: gradually tapered irregular ring mesh generated from coherent noise, not square bottom face. UV-paint with genuine lower-facade colors/stone PNG; taper width + depth independently, retain recognizable architectural front, avoid piling identical cones. Add small source-colored glowing crystals. Islands default to this option.
3. **Real arches/supports (`arches`)**: bridge arcades, arches and piers can extend visually into lower structures. Geometry openings must be true holes. `three-bvh-csg` is the preferred production boolean solution, or Blender Geometry Nodes/Boolean offline; current built-in arch script emits parametric arch ribs and separate piers (not full CSG).
4. **Atmospheric dissolution (`mist`)**: world-space multilayer animated GLSL fog fading around the foot (depth and distance aware when engine supports depth buffer), animated particles, controlled bloom on lights. **Do not clip geometry into fog with a hard straight lower boundary**; use graduated alpha or geometry taper together with fog. Distance LOD increases mist and reduces detail. `postprocessing` provides optional bloom and color grading; GLSL fallback works without it.
5. **Floating debris (`fragments`)**: spawn individually named original-palette textured 3D rock shards below structure. Independent smooth offsets/rotations, different phase/speed, no character deform. `three.quarks` optionally adds sparkle and debris trails; the included independent shard animator works without it.

### Source-faithful combination for visual depth
- Foreground: 3D masonry continuation + real buttresses + tapering boulder with PNG-derived textures.
- Midground: complete open archways + rock shards + lively magical lights.
- Background: tapered silhouette + animated volumetric-looking GLSL fog + subtle light shafts, with LOD.
- No repeated horizontal cuts. In a camera orbit 0→360°, all wall sides/roof and the foundation use authored PNG-based texture; no generic dark quads, mirrored flat backs or hollow rock bottoms.

## Working local pipeline

`png_to_glb.py` now invokes `finish_edges.py` by default and exports `*.foundation.json` as a runtime scene hint:

```bash
python skills/png-living-3d-city/scripts/png_to_glb.py input.png output/building.glb --height 24 --depth 4 --foundation auto
python skills/png-living-3d-city/scripts/png_to_glb.py input.png output/island.glb --height 12 --depth 5 --foundation rock
python skills/png-living-3d-city/scripts/png_to_glb.py input.png output/bridge.glb --height 7 --depth 3 --foundation arches
python skills/png-living-3d-city/scripts/png_to_glb.py input.png output/ruin.glb --foundation fragments --foundation-seed 112
python skills/png-living-3d-city/scripts/png_to_glb.py input.png output/far_tower.glb --foundation mist
```

For a game, import `runtime/foundation_effects.mjs` in your built/bundled Three.js project and call `installFoundationFX(THREE, glb.scene, {camera, quality:'mobile'})`. Call `update(clock.elapsedTime)` once each animation frame. It runs without Quarks or postprocessing; those are optional visual quality upgrades. For standalone HTML, inline or bundle **all** runtime assets and the local renderer; do not use a CDN.

## Open-source modules — download only what is missing

- Already in core: **Three.js (MIT)** camera, mesh, GLSL; **Blender (GPL software)** geometry; **OpenCV (Apache-2.0)** silhouette segmentation; **trimesh (MIT)** offline mesh volumes; **glTF Transform (MIT)** geometry/texture optimization. GPU effects can be built without adding more libraries.
- Optional upgrade **three-bvh-csg (MIT)** https://github.com/gkjohnson/three-bvh-csg : true cutouts and arch hollows / gothic construction geometry. Heavy geometry should be baked offline once, not boolean-updated each frame.
- Optional upgrade **three.quarks (MIT)** https://github.com/Alchemist0823/three.quarks : large dense independent particles, magic dust and crumbling fragments. For mobile, cap emitters/overdraw; game must still run without it.
- Optional upgrade **postprocessing (Zlib)** https://github.com/pmndrs/postprocessing : selective Bloom, AO, color grading, blue haze. Scene must remain legible without it.
- Optional upgrade **simplex-noise.js (MIT)** https://github.com/jwagner/simplex-noise.js : coherent noise for organic skirting, rocks, clouds. The built-in seeded numpy generator already handles offline rocks; extra dependency is not needed for this pipeline.
- **meshoptimizer** https://github.com/zeux/meshoptimizer : optimize instanced architecture and LOD for mobile.

Do not claim any optional tool is downloaded, installed or active without actually invoking it. Do not call simple static brick boxes the completed effect. The actual geometry+PNG and animated source preservation are mandatory; otherwise label preview incomplete.
