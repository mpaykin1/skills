---
name: manifold-sprite-geometry
description: >
  Optional Manifold3D Apache-2.0 native mesh preflight and explicit static CSG union for genuine original Godot/Unity GLB sprite stacking. It checks/welds GLB texture-seam vertices on temporary topology copies, preserves authored UV/color from original meshes, cooperates with Open3D or trimesh occupancy, independent sprite scene parts, and existing WebGL2 volume HTML.
---

# Manifold3D — source-preserving sprite stacking geometry

This module belongs to the existing Godot + Unity → Autonomous HTML plugin. Read `skills/sprite-stacking-priority/SKILL.md` first. All operations concern authorized original static GLBs. Do not imply the native game's GDScript/C# gameplay, materials/shaders or rigs were transferred to sprite HTML. Manifold3D can reject invalid geometry; **it is not a magic hole repair tool**.

Upstream: https://github.com/elalish/manifold — Apache-2.0. Official Python bindings in the separately installed `manifold3d` package. No native binary, patched codebase or downloaded wheels are bundled. The adapter invokes actual `manifold3d.Mesh`, `Manifold`, `to_mesh`, `volume`, and `batch_boolean(OpType.Add)`; no fake CSG algorithm.

## Integration

- Original Godot/Unity scene → authorized UnityGLTF/Godot GLB → `stack_scene_to_html.py` splits **original scene nodes** → `stack_from_glb.py` for true RGBA volume sections → Three.js WebGL2 Data3DTexture shader. Manifold's `audit` is the safe default if installed, while absent package falls back to the original source geometry, recording `manifold.used=false` in `stack.json`.
- In `normalize`, a temporary copy welds coincident vertices across UV seams **for topology only**. Manifold3D imports the closed mesh and returns candidate triangle geometry used exclusively for voxel occupancy. The **original** mesh with its UV, materials and color texture is used for RGBA sampling. Volume and bounding-box changes beyond the bounded tolerances are rejected. Open or non-manifold objects fail explicitly; no caps or artificial geometry.
- `union` combines 2–8 closed, static meshes within one GLB using Manifold3D CSG **only when explicitly requested**. Use for immobile, overlapping rubble/architectural solids. It is forbidden for gates, wheels, animated figures, vehicles with movable components, separate scene nodes that may later move independently. Colors are re-sampled from the nearest original source triangles, so actual appearance may differ. CSG is not an improvement guarantee. Validate real browser views before promotion.
- Open3D `RaycastingScene` (if installed) or the preexisting trimesh voxelizer computes occupancy. `Khronos glTF Validator` handles input structure; `Playwright + Pixelmatch` compare actual original vs derivative rendered scenes. Keep originals if visual parity fails. Grunge Horror, META GAME FUSION and Hero Animator consume the original compatible `stack.json` format without a second art generator.

## Commands

```bash
# Main entry: preserve separate GLB mesh nodes with original coordinates; audit if native is available.
python skills/godot-game-to-html/scripts/manifold_stacking.py original_static.glb --out /output/audit --manifold audit --assets-only

# Explicit topology normalization before independent object stacking.
python skills/godot-game-to-html/scripts/manifold_stacking.py original_static.glb --out /output/normalized --manifold normalize

# Only for a deliberately grouped set of immobile closed meshes — CSG union.
python skills/godot-game-to-html/scripts/manifold_stacking.py original_static.glb --out /output/union --manifold union

# Lower-level direct use, retaining existing CLI and original stack schema:
python skills/sprite-stacking-priority/scripts/stack_from_glb.py original_static.glb --out /output/slices --voxelizer trimesh --manifold normalize
```

Official install: `python -m pip install manifold3d` on an authorized build machine. Builds require NumPy, trimesh, SciPy and Pillow; Open3D is optional. `--assets-only` creates original-preserving RGBA slices/scene files without a Three.js bundle.

## Safety and scope

Never modify original files or `meta6`, never silently merge separate moving parts. Preserve original node names, global positions, raw GLB SHA, native Web export, full original animation and UI. Original translucent/complex PBR shaders remain in the original GLB/native engine. Limit input to 400,000 faces per object and 1,000,000 occupied cells; CSG union to at most 8 approved static meshes. Missing Manifold3D fails for `normalize`/`union` but `audit` keeps the existing renderer. Actual native CSG can only be claimed verified after running with the real Manifold3D package and matched browser images.
