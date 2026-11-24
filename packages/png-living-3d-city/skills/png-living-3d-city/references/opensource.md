# Open source stack for author-painted PNG -> 3D Gothic sky cities

## Extraction
- SAM2 — https://github.com/facebookresearch/sam2 — Apache-2.0 code and checkpoints; interactive/object masks.
- rembg — https://github.com/danielgatis/rembg — MIT code; model weights can have different commercial terms.
- OpenCV — https://github.com/opencv/opencv — Apache-2.0 in modern releases; connected masks, contour extraction, image cleanup.

## Geometry and depth
- Blender — https://github.com/blender/blender — GPL; offline procedural modeling, Geometry Nodes, glTF export.
- Depth Anything V2 — https://github.com/DepthAnything/Depth-Anything-V2 — Small Apache-2.0; Base/Large/Giant weights CC BY-NC 4.0, not for unlicensed commercial use.
- three-mesh-bvh — https://github.com/gkjohnson/three-mesh-bvh — MIT; spatial collision queries and custom raycasts.

## Browser rendering
- Three.js — https://github.com/mrdoob/three.js — MIT; extruded shapes, cameras, PBR and GLSL.
- glTF-Transform — https://github.com/donmccurdy/glTF-Transform — MIT; GLB manipulation and compression.
- meshoptimizer — https://github.com/zeux/meshoptimizer — MIT; optimize geometry and vertex caches.
- postprocessing — https://github.com/pmndrs/postprocessing — Zlib; composer, bloom, depth-of-field, color grading.

## Optional
- Spark — https://github.com/sparkjsdev/spark — open 3D Gaussian Splat renderer for Three.js; apply only to distant art-based visual volumes (not collision geometry), verify third-party splat content rights separately.

## Practical priority
1. OpenCV + included converter script + Three.js. 2. Blender/Geometry Nodes for actual architectural sides/recesses. 3. SAM2/Depth Anything for more automated depth and silhouettes. 4. glTF-Transform/meshoptimizer to keep city scalable. Optional splats only after polygonal gameplay works.

## Architectural ends — new source-aligned integrations

- three-bvh-csg — https://github.com/gkjohnson/three-bvh-csg — MIT; Boolean arches/undercuts, offline bake suggested.
- three.quarks — https://github.com/Alchemist0823/three.quarks — MIT; floating debris sparks, blue magical particle shafts.
- simplex-noise.js — https://github.com/jwagner/simplex-noise.js — MIT; procedural stone/noise optional if built-in seeded rock mesh is insufficient.
- Included built-in `scripts/finish_edges.py` and `runtime/foundation_effects.mjs` provide the five foundation looks without needing additional dependencies.

Mandatory design contract: `references/foundation-completion.md`. Every building bottom needs semantic completion, never a horizontal cut.
