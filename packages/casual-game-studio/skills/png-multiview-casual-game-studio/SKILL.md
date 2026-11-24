---
name: png-multiview-casual-game-studio
description: Mandatory preservation of drawn PNG architectural identity when converting painted buildings, bridges, towers or cities into actual 3D geometry with navigable camera. Reconstruct distinct PNG textures for every visible side and rear.
---

# PNG ARCHITECTURE MULTIVIEW — NON-NEGOTIABLE RULE

Activate on every workflow converting a user-supplied PNG/JPEG painting or spritesheet of a building, tower, castle, bridge, street or city into three-dimensional architecture, including Three.js, GLSL, Blender, GLB and voxel/cutout-game pipelines. The original source may only depict a front facade. **Do not require the input to contain hidden sides.** Instead reconstruct them as NEW PNG assets derived from source style and geometry.

1. Preserve the user's painted **front PNG pixels and architectural landmarks** where visible. Never silently replace the original facade with generic boxes, procedural bricks or unrelated illustrations.
2. **Generate and deliver five separate PNG textures for each 3D building**: `front.png` (approved original cutout), `left.png`, `right.png`, `rear.png`, `roof.png`. Infer missing views by recomposing authentic source motifs, linework, palette and openings; record which are inferred. Additional user-provided views take priority. Never pass a front flip, solid color side or decal as the completed hidden view.
3. Build **real 3D volumetric geometry** with side/back/roof faces, UV unwrap each with its corresponding PNG. Maintain cross-view proportions of windows, balconies, domes, clockfaces, stairs, buttresses, portals, pointed spires and bridges. For transparent atlases, cut out all independent assets; for white JPEG atlases, remove the white background and fringes, including openings below arches.
4. Keep the SAME building recognizable from front, left, right, rear and elevated view. Verify camera orbit at yaw 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315° plus a roof view, checking silhouette continuity, occlusion and correct texture seams. From absent source information, mark results as **artistically inferred**, never as geometrically exact.
5. **Reject release** if any expected PNG view is missing, side/rear is untextured, a painted façade becomes anonymous 3D primitives, UVs stretch recognisable ornaments, camera reveals billboard cheating, or source identity changes during movement. Mark preview incomplete rather than claiming all-angle acceptance.
6. Persist `building.views.json` with input SHA-256, output texture paths, per-face provenance, UV map names, dimensions, and shared architectural identity anchors; do not overwrite user originals.
7. This architectural rule applies when PNGs become *volumetric buildings*. It does not mandate 3D reconstruction for ordinary 2D sprite/character animation. Preserve Hero Animator's unchanged identity and prerecorded action frames. Do not animate any character without player input when it is player-controlled.
8. For full games: use LOD, texture atlases/KTX2, instance repeated elements, stream chunks for unbounded travel, preserve unique source-derived façades, animate light/weather/doors/windows independently, and support desktop and portrait/landscape mobile.

Preferred helper: `png-living-3d-city` authored plugin. It provides an open-source pipeline for image extraction, source-derived PNG facades, UV-mapped 3D GLB and city assembly. Invocation is a reference, not a declaration that another plugin is already installed or automatically available.
