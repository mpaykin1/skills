# Monster Anatomy 3D — Hybrid 3D + True Sprite Stacking (v2.1.0)

**Mandatory default**: visible monster flesh, musculature, skin and main silhouette are CPU-baked **independent volumetric RGBA sprite stacks**. The *same original* skinned GLB is kept hidden from the color pass to supply a real animated skeleton, dynamic 3D shadow casting, socketed accessories, and collider geometry. Do not create a second visible body, switch character identities when attacking, or substitute a flat GIF/billboard for the stack. Preserve artist-approved geometry, PBR textures, actions and `.blend` files unchanged.

## One command, CPU only

```sh
python scripts/build_with_anatomy.py --blender blender --output-dir build/monster-hybrid
```

Requires Blender 4.5+ installed; 3D stack CPU operations require `numpy`, `scipy`, `trimesh`, `Pillow`. It builds original anatomical model as before, bakes all existing bone actions, copies a **byte-for-byte** original GLB to `monster_sprite_stacking/hybrid/original_rig.glb`, writes normal/roughness atlases and copies runtime JavaScript. No CUDA, NVIDIA GPU, server API, pretrained weights or network required when dependencies are installed.

For an already-approved GLB static model, Blender is unnecessary:

```sh
python scripts/build_sprite_stacking.py --input-glb monster.glb --output build/monster-hybrid
```

For an animated `.blend`, the same GLB is required so Blender rig clips, socket transforms and volume timelines match:

```sh
python scripts/build_sprite_stacking.py --input-blend monster.blend \
  --hybrid-glb monster-animated.glb --blender blender --clip ALL \
  --output build/monster-hybrid
```

The GLB and Blender source MUST describe the **same rig and posed character**. Divergent glTF animation names or model transforms fail the runtime consistency checks; do not automatically guess retarget mappings. A compressed GLB needs the game's existing Meshopt/Draco loaders. Build CPU script deliberately bundles the **uncompressed authored** GLB before optional compression, for reliable WebGL2 loading.

The original `.blend`, `.glb` and geometry are never overwritten. If hybrid GLB is missing, only a legacy stack can be produced; do not claim working shadows or socket effects.

## Artist object naming (no repeated body in camera)

- `MONSTER_RIG`: the single original Blender armature and source bone animation. All BODY/MUSCLE/SKIN meshes are baked as sprite volumes and **hidden from color rendering** at runtime but still cast real 3D shadows.
- `HYBRID_3D_*`: only expressly approved horns, claws, tongue, chains, dangling props, weapons and other physically important attachments stay visible as actual meshes. Their GLB skeleton/bone parenting drives them. These names are **excluded** from sprite-volume baking to prevent double depiction. `HYBRID_ATTACHMENTS` collections are excluded too.
- `COLLIDER_*`: collision-only sources, never rendered. Games can read these objects and create their own physics bodies. A GLB mesh is not itself a Rapier collider until the game explicitly constructs it.
- `SHADOW_PROXY_*`: optional artist-authored invisible shadow geometry is excluded from visual sprite baking; existing skinned body is already a legitimate default shadow proxy.
- `attachToBone('BoneName', object3D)` inserts real 3D accessories or particle emitters on source bones. FX such as eyes, blood, saliva, smoke and illumination are real 3D/effect objects supplied by the game — the bridge doesn't pretend to synthesize them automatically.

**Important**: all excluded authored attachment meshes must be included in the final exported GLB. If the Blender GLB export excludes them, the runtime can only attach objects provided by game code. No invented accessories.

## Render architecture

1. Blender exports evaluated deformed body meshes per actual rig action/pose. Every action shares one geometry grid, XYZ spacing, world pivot and scale. `poses.json` records original action frame start/end and real scene FPS so `clip.json.durationSeconds` and pose timestamps align with the GLB timeline. No image stretching or fake motion.
2. Trimesh + SciPy + Pillow generate exact-occupancy RGBA horizontal slices; `stack.atlas.png` includes the actual body appearance; `stack.surface.png` packs CPU occupancy-gradient **outward normals** (RGB) and an author-controlled **roughness** value (A). The underlying occupancy geometry is not blurred. This is normal-assisted approximate lighting, *not* a physically measured PBR material or photometric reconstruction.
3. `runtime/sprite_stack_three.js`: one WebGL2 `Data3DTexture` per animation pose, raymarched from any direction. Volume writes `gl_FragDepth` so real horns, claws and world geometry occlude correctly. Shader uses the **derived normals** and roughness for local directional lighting, wet specular response and rim light. Without a surface atlas, old v2.0 stacks continue using occupancy-gradient normals.
4. `runtime/hybrid_monster_three.js`: loads the original GLB via the app's `GLTFLoader`. All source body materials are cloned with `colorWrite=false` and `depthWrite=false`, while `castShadow=true`. Original `SkinnedMesh` remains in the scene; the hidden body follows exactly the action synchronized to stack time. Whitelisted 3D attachments keep their own materials, lights, transforms and shadows.
5. Phase lock: `AnimationMixer` gets the corresponding original GLB clip time at the same fractional phase as the sprite stack. Actions are mapped by exact name or explicit `clipMap`. If an animation is missing, fail rather than playing unrelated motion. Idle runs only if the game explicitly starts it; attack runs only on attack input.
6. The complete actor uses one Three.js root and a consistent transformation. The default transforms authored Blender +Z-up stack to glTF +Y-up; bounds must match. Explicit bone attachment API and collider node list are available to the game. The game must enable `renderer.shadowMap.enabled=true` and set `light.castShadow=true`; otherwise there are **no** visible dynamic shadows. This is not full-body ray-traced shadows.
7. Performance: per-frame RGBA+normal/roughness volumes require approximately `8*nx*ny*nz` bytes. The loader defaults to one cached action and rejects too-large animation volumes; `setQuality('mobile')` reduces ray samples. High-fidelity requires sufficient phone memory and WebGL2 — check FPS and orientation with the target device.

## Three.js integration (app provides existing local `three` and addon packages)

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { loadHybridMonster } from './monster_sprite_stacking/runtime/hybrid_monster_three.js';

// Build your existing renderer, scene, camera and light. Shadows are opt-in.
renderer.shadowMap.enabled = true;
light.castShadow = true;
const monster = await loadHybridMonster(THREE, {
  GLTFLoader,
  libraryUrl: '/assets/monster_sprite_stacking/library.json',
  attachmentPrefix: 'HYBRID_3D_',
  strictAnimation: true,
  wetness: 0.30,
  maxCachedClips: 1,
});
scene.add(monster.group);
await monster.play('IDLE_BREATH');
// In one existing game animation loop: monster.update(deltaSeconds)
// Player move input: await monster.play('STALK_LOOP')
// Player attack input ONLY: await monster.play('GRAB_ATTACK')
// monster.attachToBone('RightHand', preexistingClawMesh)
// monster.colliderMeshes: original COLLIDER_* geometry references for physics
```

This is an **ES module**, not a standalone CDN-powered game. Three.js is not included or downloadable by this skill; use the local Three.js dependency already present in the game. Browser playback uses WebGL2 and a local server/website (`fetch()`), not arbitrary `file://` CORS. No GPU is required for **asset generation**, but Three.js/WebGL2 rendering **does** use the device graphics processor. Never claim CPU-only WebGL rendering.

## Output structure

```text
monster_sprite_stacking/
  library.json                         rigGLB URL, clips, author-approved identity
  hybrid/original_rig.glb             byte-identical hidden rig + accessories source
  runtime/sprite_stack_three.js       WebGL2 volume shader
  runtime/hybrid_monster_three.js     rig/attachments/shadow/sync binding
  stack/IDLE_BREATH/clip.json         phase-correct authored pose timeline
  stack/IDLE_BREATH/pose_000/
    stack.json                         pivot, grid, material map fields
    stack.atlas.png                    real RGBA occupancy & source colors
    stack.surface.png                  volumetric normals + roughness
    layers/000.png ...                 exact original shape horizontal slices
  stack/STALK_LOOP/...                completely independent rig poses
  stack/GRAB_ATTACK/...               only rendered after game attack input
```

## Compatibility & limits

- Old v2.0 `stack.json` without `surfaceAtlas` remains valid. `--no-hybrid` retains sprite-only render and disables hidden rig and its claimed features.
- The stack is deliberately **discrete** across independently baked frames. The source rig interpolates continuously; close-up high-speed changes can show mismatch between frames. Sample additional poses for closer synchronization rather than warping artwork. Frame timestamps and source GLB clips must correspond.
- Original GLB animations must be exported and maintain a matching clip name; optional explicit `clipMap` fixes renamed exports. The original Blender exporter is not known to preserve NLA action naming in every version; review the GLB clips in your game.
- Spatial shadow projection comes from the original smooth skinned mesh, not the discrete voxel shell, so silhouettes can differ slightly at animation boundaries. Require camera/lighting preview before approving a hero.
- `Pillow` cannot invent true photographic normal maps or reconstruct an unknown monster from one portrait. The normal atlas is a gradient of actual captured occupied volume, not the authored tangent-space normal map in the original glTF.
- Synthetic technical source included in the plugin demonstrates **real CPU volumes and normal atlas**, but not a complete animated Blender monster. Actual browser/WebGL2 + Blender animation synchronization is not verified in this environment (Blender and local `three` package unavailable). Do not claim an in-game visual PASS before observing it in-game.
