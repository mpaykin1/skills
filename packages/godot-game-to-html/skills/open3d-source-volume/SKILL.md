---
name: open3d-source-volume
description: >
  CPU Open3D RaycastingScene volume extraction for existing Godot/Unity original GLBs into genuine horizontal transparent RGBA sprite stacks. Compatible with the Godot + Unity -> Autonomous HTML skill, Sprite Stacking Grunge Horror, Meta Game Fusion and Hero Animator. Original models, textures, game scripts and animated rigs remain untouched.
---

# Open3D original-mesh volumetric stacking — META GAMES

**New optional source-volume stage, not a new game engine.** Read `../sprite-stacking-priority/SKILL.md` as primary contract. Use the existing `scripts/stack_from_glb.py` with `--voxelizer open3d` to require actual official Open3D (MIT, installed externally). Default `auto` chooses Open3D if present and the original `trimesh` voxelizer otherwise. No fake image extrusion or additional plugin installation needed for the fallback.

## Original-asset 3D pipeline

`Godot/Unity/UnityGLTF original static GLB → Open3D CPU RaycastingScene distance+occupancy → old SciPy/trimesh nearest original surface colors → unchanged RGBA horizontal slice contract (stack.json/layers/NNN.png) → existing Three.js WebGL2 volume renderer → original Pixelmatch/Playwright visual gate.`

Open3D `compute_occupancy(..., nsamples=3)` is used **only** on real watertight triangular meshes, one mesh per raycast scene; `compute_distance` preserves cells near the actual surface. Nonwatertight/open objects may be represented ONLY by their actual thin shells when `--allow-shell` is passed; holes and hollow gaps are not filled with invented mass. Binary occupancy must never be used to replace source alpha-blended glass, volumetric fog or original shader effects. Per-mesh bounds, 65536-point query batches and the existing <=1,000,000 occupied-voxel, <=6,000,000 grid-cell budgets limit CPU/memory. Original animation/skinning remains with GLB or manually approved full-pose volumes.

## Executable integration

```bash
# Existing CLI now automatically prefers Open3D when installed:
python skills/sprite-stacking-priority/scripts/stack_from_glb.py ORIGINAL.glb --out OUT/volume --xy 192 --z 96 --allow-shell
# Strict Open3D mode, fails rather than imitating its result if library missing:
python skills/sprite-stacking-priority/scripts/stack_from_glb.py ORIGINAL.glb --out OUT/volume --voxelizer open3d
# Force legacy fallback for comparison:
python skills/sprite-stacking-priority/scripts/stack_from_glb.py ORIGINAL.glb --out OUT/legacy --voxelizer trimesh
# Scene-splitting and visual HTML keep invoking the same converter:
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py ORIGINAL.glb --out OUT/scene
```

The Open3D package itself is **not bundled**. The output stores `voxelizer`, the original GLB SHA256, original world frame and material color sampling; all previous scene/nexus/Grunge sprite stack consumers continue reading the same format.

## Cooperating skills

- **Sprite Stacking Grunge Horror:** supplies real original PNG slices or approved textured source GLB; nothing is recolored or replicated.
- **Meta Game Fusion / game-style-forge:** consumes the actual `stack.json` volumes in Three.js, but Rapier/GLB retains true physics and original collision shapes.
- **Blender Model Animation Enhancer:** prepares authentic source mesh and original UV; no retopology or remeshing without explicit approval.
- **Hero Animator:** original full-body character clips keep fixed identity; raycast stacking only for static meshes or separately approved whole-pose rigid volumes.
- **Khronos Validator + Playwright/Pixelmatch:** block promotion if original geometry data or browser appearance is degraded.
- **Manifold3D:** a future **opt-in** topology repair stage for invalid watertightness; do not invoke on open authored ruin meshes without review.

Use Open3D for geometry occupancy and existing SciPy for UV/material color. It cannot reconstruct missing source polygons or convert gameplay to HTML. No claims of browser fidelity until matched renders are checked. Avoid extra reports/tests/evidence not requested.
