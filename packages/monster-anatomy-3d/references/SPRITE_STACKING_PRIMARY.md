> **Default v2.1 hybrid:** see [HYBRID_3D_SPRITE_STACKING.md](HYBRID_3D_SPRITE_STACKING.md). The original rig provides real 3D shadows and socketed details while visible body remains volume-stacked.

# Sprite Stacking FIRST — Monster Anatomy 3D v2.1.0

**Primary visible technique for all future monsters and their parts**: true CPU-baked volumetric sprite stacks. Do not substitute a flat billboard, a camera-facing image plane, a single PNG stretched into slabs, a sprite sheet of unrelated angles, or generic voxels replacing the character. Source-of-truth anatomical mesh, sculpted muscle forms, skeleton, pose clips, texture UVs, and fitted physics are preserved. **The main visible organic character surface** is intended to render via stacked RGBA geometry volumes in Three.js; actual rigging and collision may remain native 3D and invisible.

## Effective order / how old sources strengthen one another

1. Reference and proportions → Z-Anatomy / MPFB2 (advisory only), MyoGeneratorRemix (original muscle meshes), Blender (approved anatomy), Manifold3D (optional sculpt reference). Never replace the approved monster with donor geometry.
2. PyMeshLab + Trimesh check open/degenerate geometry; Instant Meshes makes CPU topology LOD, xatlas sets UVs; Pillow renders/bakes material textures. Protected skinning SciPy plus Rigger/Open Mocap plus existing Blender shape-key/NLA clips generate the **actual evaluated geometry at each pose**. No image warp or made-up movement.
3. Export snapshots with `scripts/export_sprite_poses_blender.py`. On Blender 4.5+, the script selects existing MONSTER_RIG actions (`IDLE_BREATH`, `STALK_LOOP`, `GRAB_ATTACK`, user-named MOCAP_/RIGGER_ clips) and writes evaluated OBJ+MTL geometry. One pose snapshot per frame; clips never mix. Output includes original material references when representable by OBJ; Blender texture nodes that OBJ cannot export require albedo baking first.
4. Run `scripts/sprite_stack_cpu.py`. Real `trimesh.voxelized(...).fill()` handles watertight rest-pose/deformed geometry; SciPy KDTree maps original triangle/vertex/UV base colors onto occupied cells, with Pillow writing ordered transparent RGBA `layers/000.png..` and `stack.atlas.png` from exactly the same volume. The shared dimensions, pivot and pitch across **all clips and poses** prevent scale jumps (the build creates shared_grid.json). NO GPU/CUDA. UV-to-voxel coloration from nearest triangle centroids is approximate, not guaranteed pixel-perfect at texture seams.
5. One reusable `runtime/sprite_stack_three.js` loads the pose atlases as `THREE.Data3DTexture` and raymarches their 3D alpha occupancy using a genuine WebGL2 GLSL volume, not plain stacked quads. Works from above, below, rear, sides, obliques. Pixel depths use `gl_FragDepth`, enabling world occlusion. 3D normals are estimated from occupancy gradients, with spatial lighting. No decoder/CDN required by the custom shader itself, but the game supplies a local Three.js build.
6. For games choose each action explicitly via `await controller.play('STALK_LOOP')` / `await controller.play('GRAB_ATTACK')`. Never auto-trigger combat, duck or jump. Default library loads the first idle/static frame without acting. Preserve monster identity across every action by deriving all frames from the same Blender source/rig.
7. `scripts/render_sprite_stack.py` produces true depth-ordered transparent 360 GIF and front/back/left/right/top/bottom previews from all source slices (not fake orbit screenshots). Each PNG/slice and frame is uniquely generated and tied to real 3D geometry. Gameplay animations come from pose volumes, not GIF playback.
8. glTF-Transform, gltfpack and Khronos Validator remain for the retained animated GLB (physics/fallback/portable 3D authoring source); they do not optimize sprite PNG volumes. Original `.blend`, `.glb`, materials, UVs, NLA tracks and clips are never overwritten.

## Commands

CPU-only existing 3D source, no Blender needed:

```bash
python scripts/build_with_anatomy.py --sprite-source existing-monster.glb --output-dir build/new-monster
```

CPU-only existing animated Blender monster, export **all real bone actions** automatically (requires Blender 4.5+, `numpy`, `scipy`, `trimesh`, `Pillow` in external Python):

```bash
python scripts/build_sprite_stacking.py --input-blend monster.blend --blender blender --clip ALL --output build/new-monster-stacks
```

Full CPU anatomical scene build now **defaults to true sprite stacking** in addition to immutable `.blend`/`.glb`:

```bash
python scripts/build_with_anatomy.py --blender blender --output-dir build/monster
```

Quality settings: `--sprite-xy-size 128 --sprite-z-slices 96 --sprite-frames 16` in the main command. A standard default uses `96x96x64` cells and 12 baked frames for mobile. For very high fidelity use up to `256x256x128` (may consume much RAM and create large assets). For static input use `build_sprite_stacking.py --xy-size ... --z-slices ...`.

A legacy pure GLB output is available only when explicitly `--no-sprite-stacking` (e.g. when the model is an open sheet or texture-only alpha glass and true stack cannot be authored). Don't silently switch back to primitive geometry or planar images.

## Outputs

```
monster_sprite_stacking/
  library.json                      all available authored clips
  stack/
    IDLE_BREATH/
      clip.json                     frames+FPS, stable pivot and dimensions
      pose_000/stack.json           spacing + ordered PNG layers
      pose_000/stack.atlas.png      single load-friendly per-pose RGBA atlas
      pose_000/layers/*.png         transparent true horizontal slices
      pose_001/...                 next real posed geometry
      preview/orbit_360.gif        actual 3D orbit
    STALK_LOOP/...                  its own true 3D slices
    GRAB_ATTACK/...                 explicit attack only
```

## Limitations / fail-closed conditions

- Single images are **not** a 3D source. First create/obtain and approve a true 3D volume; missing back geometry is invented only with clear disclosure. Reusing a flat picture for all slices or all 360 views is forbidden.
- `voxelized().fill()` requires a watertight closed surface. Open meshes stop unless explicitly `--sprite-allow-open`, which stores a thin shell rather than claiming an internal solid. Thin fingers/tendrils require increased slice resolution or separate articulated parts; never crop/disappear them silently.
- Alpha is for empty/occupied cells; translucent skin and refractive glass are not physically modeled. For their true optical transparency, use a separately approved technique rather than claiming volumetric glass.
- Texture colors in posed OBJ material exports can be limited by Blender OBJ format. v2.1 adds a separate `stack.surface.png` atlas with CPU-derived XYZ normals and an author-controlled roughness; this is approximate directional/PBR-inspired lighting, not a replacement for original tangent-space normal maps. Keep high-fidelity glTF PBR as an authoring reference, and bake albedo before slicing if needed.
- All frames share one 3D pivot, scale and fixed world coordinate system; movement is actual posed mesh per frame. Pose playback is discrete, not continuous skeletal interpolation on a billboard. Sample more frames for smoother movements. No optical flow/character substitution.
- A real Three.js/WebGL2 integration must be checked on the actual intended phone/browser and may need LOD scaling, frustum culling and lowering the number of simultaneous active 3D textures. Shader has a finite 512-step raymarch budget. Never claim universal 60 FPS without measurement.
- Blender is absent in the build sandbox, so animated Blender pose export and Three.js browser runtime have not been end-to-end verified. Only static stack CPU generation and its orbit output were exercised. Fail honestly if dependencies are unavailable; no fake PASS.

## Attribution

Inspired by the user's `Sprite Stacking Grunge Horror` skill production rules. Uses local original adapter logic, not copied upstream artwork. Underlying Trimesh MIT, Pillow MIT-CMU, SciPy BSD-3. No third-party imagery bundled. Original GG scene's license stays with its owner.

## Three.js (existing local `three` ESM dependency)

```js
import * as THREE from 'three';
import {loadSpriteStackLibrary} from './runtime/sprite_stack_three.js';
const actor=await loadSpriteStackLibrary(THREE,'/assets/monster/library.json');
scene.add(actor.group); // source +Z-up converted to default Three.js +Y-up
await actor.play('IDLE_BREATH'); // explicit user/game choice
// In the game's frame loop: actor.update(clock.getDelta());
// On player movement: await actor.play('STALK_LOOP');
// On player attack input ONLY: await actor.play('GRAB_ATTACK');
// For a +Z-up world use {worldUp:'Z'} as the third argument.
```

`THREE.Data3DTexture` requires WebGL2; run via localhost or in the shipped game, not `file://` if fetch/CORS is restricted. Three.js is not bundled; use the game's already-approved locally hosted Three.js. No billboard geometry is created. If the device lacks WebGL2, fail transparently or use an explicitly approved GLB fallback.
