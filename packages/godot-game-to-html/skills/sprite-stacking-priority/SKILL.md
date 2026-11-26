---
name: sprite-stacking-priority
description: >
  Mandatory stack-first original Godot/Unity/GLB visual conversion. Maximize genuine sprite stacking from horizontal RGBA volume slices for scenery, props, mechanisms, terrain and full-pose animated entities, using MIT trimesh + SciPy/Pillow and locally bundled Three.js WebGL2 3D-texture DDA. Compatible with the existing Sprite Stacking Grunge Horror stack.json contract. Never replace original gameplay or forge depth from one image.
---

# SPRITE STACKING FIRST — Godot + Unity → Autonomous HTML

**Default for new visual worlds: use TRUE sprite stacking wherever original 3D geometry or authentic volume slices exist.** Keep Godot/Unity native WebGL as the only default way to preserve playable source game logic. Visual stacking must never be described as porting GDScript/C#, physics, AI, damage, inventory, UI, or state machines.

## Priority selection — maximize stack-covered graphics

1. **All authored static 3D objects** with mesh/UV/vertex color → stack: architecture, walls, gates, columns, bridges, furniture, vehicles, machinery, rocks, ruins, props, floor decoration. For composite structures, create separate moving stacks for individual gates, wheels, and doors; apply rigid transforms, NEVER stretch sprites or clone one PNG to fake volume.
2. **Thin/nonwatertight source meshes**, like grasses, fences, signs or sheet-metal panels → preserve original shell voxels via `--allow-shell` rather than inventing solid interior. Preserve source holes/negative space; if texture/shape unsupported or visually degraded, keep original 3D mesh for that object.
3. **Animated creatures/heroes/people** → only approved and genuinely different full-body 3D slice volumes per authored pose/frame, with identical pivot, dimensions, scale and hero identity. `scene.json` may declare `frames` and `fps`; renderer swaps full volume textures, NOT vertex deformation, cutout warping or one-image fakery. Without independent authored frames retain source GLB skeletal animation. Integrate with Hero Animator safeguards.
4. **Organic/volumetric alpha, fog, rain and translucent characters** → do not flatten or destroy optical properties. True sprite stack binary occupancy is for opaque forms; keep native original shader/FX or a separate approved voxel-volume implementation when appropriate. Weather lives in independent dynamic depth layers; sounds and screen overlays are not stacked geometry.
5. **2D-only source PNG/GIF** without authentic depth → PixiJS and the user's approved full-frame sprites, not fake extrusion into 360° geometry.

Stack coverage is by **actual scene objects that survive visual comparison**, not raw number of fake layers. Keep a reversible mapping from each stack to its original GLB with SHA-256 and consistent transforms; keep original output unchanged. Reuse one volume resource across repeated instances; cap total resident voxel bytes. Mobile FPS below 30 → lower deliberate resolution/LOD and draw cost, never replace approved model silhouettes with arbitrary low-poly props.

## End-to-end pipeline

### Source original static GLB → real slices → offline volumetric HTML

```bash
python skills/sprite-stacking-priority/scripts/stack_to_html.py ORIGINAL.glb --out /output/stacked
# or canonical Godot/Unity single entry:
python skills/godot-game-to-html/scripts/universal_game_to_html.py ORIGINAL.glb --out /output/stacked --mode stacking
```

- `stack_from_glb.py`: **trimesh** analyzes actual transformed mesh triangles and fills a 3D voxel grid where the source mesh is closed; open shells stay shells. **SciPy cKDTree** and nearest surface barycentric UV sample the existing PNG/PBR texture or vertex color; **Pillow** writes genuine bottom→top RGBA PNG sections (default XY 192, Z 96, bounded by source extent). No generated/repeated patterns or improvised colors. Grunge Horror texture remains the authored original, unless the user requests a separate artistic transformation.
- `stack.json`: same schema used by existing `sprite-stacking-grunge` skill: `layers`, `spacing:[dx,dy,dz]`, `pivot:[x,y,z]`, `size`, axes **+X right, +Y forward, +Z up**; keep source SHA256, occupancy, grid dimensions. Layers are all the **same pixel size**. Never present independent camera snapshots as true slices.
- `stack_to_html.py` packages one or many real stacks. `stack-runtime.mjs` uses **Three.js Data3DTexture** and a WebGL2 fragment-shader **3D-DDA occupancy traversal**: full yaw 0–360°, tilt to directly above/below, proper volume visibility, depth buffer output (`gl_FragDepth`), original color/alpha occupancy. No billboard/identical plane cloning; source-independent texture detail is not generated.
- Runtime HTML embeds the actual RGBA data and locally bundled pinned `three@0.187.0` through `esbuild@0.25.5`. **No CDN at runtime**. Build requires Node/npm once to obtain versioned dependencies, and Python numpy/trimesh/scipy/Pillow. `--no-install` avoids all build-time downloads. GPU WebGL2 is required for 3D textures; failing devices must use native WebGL/GLB/Pixi fallback and never fake a PASS.
- `--mode visual` is **stack-first** for GLB/Unity source, with transparent fallback to existing GLB viewer if volume conversion is impossible. `--mesh-visual` forces previous intact Three.js GLB viewer; with `--ktx-manifest`, keep Basis/KTX2 texture-specific route. `--mode stacking` refuses invalid original geometry instead of substituting a fake object.

### Already-authored sprite stacking objects

```bash
python skills/sprite-stacking-priority/scripts/stack_to_html.py /approved/stack.json --out /output/stack.html
```

Supports any actual `stack.json` authored by the user's **Sprite Stacking Grunge Horror** skill, including its 64–128 or more real horizontal PNG slices. All slices are used; do not render just GIF previews. Preserve 360° fidelity by reading the original volume, not independent 2D angle sheets.

### Many objects, interactive pose volumes, independent parts

Provide a scene JSON:

```json
{
  "stacks": [
    {"stack":"gate/stack.json","position":[0,0,0],"rotation":[0,0,0],"scale":[1,1,1]},
    {"stack":"monster/idle/stack.json","frames":["monster/run1/stack.json","monster/run2/stack.json"],"fps":12,"position":[5,0,0]}
  ]
}
```

Every animation frame must be a separately authored **complete spatial voxel stack** with same dimensions, spacing and pivot. Repeated instances share decoded volume textures. The standalone HTML plays a visual pose cycle; character movement, collision and gameplay must come from the original engine/game state in a full playable integration. Never trigger attacks automatically.

## Fidelity and fail-closed rules

- The stack converter refuses missing original authored color, skinned / animated GLB, too many triangles/voxels, invalid geometry, missing true PNGs, and unsigned/unknown sources; it does NOT claim to manufacture original hidden details. If input is a 2D reference without complete depth, only build what is grounded and mark newly inferred faces as reconstructed.
- Preserve original game engine WebGL and GLB alongside stack derivatives; original 3D appearance and shader features may be lost by voxelization. All colors are samples from existing author material, not a perfect inverse of the original render. Use Khronos glTF Validator and Playwright + Pixelmatch on matched real-browser views before treating any sprite version as visually acceptable.
- `xatlas`, Blender AO, Intel OIDN, OpenImageIO and oxipng can improve only approved static derivative lightmaps and PNGs; `KTX2/Basis` may encode separate tested candidates, not alter original 3D volume data silently. `UnityGLTF` supplies source GLB; `GDRETools/AssetRipper/UnityPy/ILSpy/Cpp2IL` supply authorized content/code; Three.js, PixiJS and Rapier retain their own distinct roles.
- Preserve legal provenance and third-party MIT/BSD/Apache notices, no protected `meta6` writes. Do not invent a deployed game URL or label visuals a full gameplay port. Do not create unsolicited reports, tests, handoffs or evidence.
