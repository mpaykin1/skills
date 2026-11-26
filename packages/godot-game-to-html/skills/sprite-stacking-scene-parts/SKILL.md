---
name: sprite-stacking-scene-parts
description: >
  Source-authentic, scene-level sprite stacking of original Godot/Unity static GLB assemblies. Preserves distinct doors, bridge parts, machinery and architecture as separately transformable true RGBA-volume stacks with original source SHA256; offline Three.js WebGL2 DDA visual HTML and manually controlled full-volume pose playback. Must not replace original engine gameplay or forge missing hero poses.
---

# Sprite Stacking Scene Parts — companion to Godot + Unity → Autonomous HTML v1.18

**Use this by default when the source contains multiple original 3D objects, not one GLB for each entire scene.** This is an extension of the already installed `sprite-stacking-priority` skill, not a second or competing renderer. The original Godot/Unity engine WebGL build remains authoritative for gameplay, physics, C#/GDScript, user actions, and source-level FX.

## Actual entrypoint

```bash
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py ORIGINAL_SCENE.glb --out OUT
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py ORIGINAL_UNITY_PROJECT --out OUT --unity /path/to/Unity
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py /approved/stack.json --out OUT
```

- **GLB scene**: `stack_scene_parts.py` reads every actual `scene.graph.nodes_geometry` and its 4×4 transform using `trimesh`, makes a separate non-destructive original mesh instance for each node, and calls the existing real `stack_from_glb.py` voxelizer on each. No fake mesh/extruded painting and no invented colors. Existing per-voxel UV/vertex-color sampling, holes and shell mode are reused, not duplicated.
- **World composition**: produces `scene.json` with the exact number of successfully converted nodes, `parts/*/source-part.glb` and `parts/*/volume/{stack.json,layers/*.png}`. Original GLB SHA256, original node name and transform are preserved in each stack. Uses the same `stack_to_html.py` for one offline scene HTML. Separate original nodes remain independent 3D volume objects, so approved rigid-part motion can be wired to game logic later.
- **Unity**: the already installed Khronos UnityGLTF exporter supplies the source scene GLBs first, then each source scene is converted in an independent area. No C#/IL2CPP gameplay is claimed in the resulting HTML visual scene.
- **Authored stacks/poses**: an approved Sprite Stacking Grunge Horror `stack.json` or animation scene JSON uses existing `stack_to_html.py` unchanged. Do not process user-supplied 2D character paintings as depth volume without an original 3D source. Original full-body frames must share dimensions, pivot and spacing. Pose playback now starts **paused** and begins only when the user presses `▶ Позы`; no automatic character attack or sprite-warp.

## WebGL2 correctness and visual identity

- Existing Three.js 0.187.0 + Data3DTexture uses actual individual RGBA XY cross-sections as a 3D field with 3D DDA. Upgraded `stack-runtime.mjs` samples exact integer texels, calculates the first occupied **voxel face** for `gl_FragDepth`, handles exactly axial camera rays, supports orbit/zoom/360 views and adaptive pixel ratio. It is not a billboard or repeated stack planes.
- Default display is original unshaded material color. Optional `Свет: рельеф` adds **only a reversible side-light shading approximation**, not automatically changed albedo textures or a claim to have reconstructed original volumetric shaders.
- The renderer refuses missing/bad alpha bytes, a too-large 3D texture for the GPU, or mismatched full-body pose volumes. If WebGL2 is unavailable, use the existing original GLB/engine renderer, not a fake Canvas substitution.
- Maximum 32 unique scene nodes/volumes and 128 MiB raw RGBA across one HTML scene, consistent with the existing stack runtime. If over budget, fail explicitly; divide large originals into meaningful authored areas. Do not quietly drop parts, cap NPCs or erase the environment.

## Skills that cooperate; no duplicate physics or art

- `Sprite Stacking Grunge Horror` authors genuine manually approved material/slice packs in the existing `stack.json` format.
- `Meta Game Fusion` owns Three.js runtime/game physics integration: actual Rapier colliders, Recast navigation, character decisions and depth-correct opaque stacks; voxel masks are **visuals only**.
- `Hero Animator` supplies verified independent full-body pose frames, input-only attack/roll/jump and stable hero identity. A 2D animation without authentic slice volumes stays 2D/PixiJS or original GLB, never an invented 3D hero.
- `Blender Model Animation Enhancer` supplies original static/dynamic GLB with correct names, transforms, UVs, approved geometry and animation; animated meshes lacking approved pose stacks keep skeletal rendering.
- `Game Style Forge` supplies optional original-theme weather/GLSL lighting/postFX **around**, not painted into, the original voxel textures.
- `Skill Nexus` passes assets using original SHA256 and explicit art/rights provenance. A stack is an asset, not proof of complete native gameplay.
- `Khronos glTF Validator` checks original/derivative geometry and images, while `Playwright + Pixelmatch` checks matching browser screenshots. Structural validity does not imply visual similarity. In heavy random fog/snow, synchronize time and camera or declare parity inconclusive.

For UI and mobile in playable games apply the installed `animated-world-guard`: correct portrait/landscape sizing, touch controls, continuous authored NPC motions; never invent a game for lack of genuine assets. A static scene preview must be labelled *visual-only*. No unsolicited reports, handoff or evidence files.
