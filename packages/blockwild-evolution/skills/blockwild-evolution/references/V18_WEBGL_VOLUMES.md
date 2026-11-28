# BLOCKWILD v18 — WebGL2 Source Volume Stacking

## What is actually integrated

- Four author-defined character identities × five full-body source-volume poses = **20 independent physical occupancy volumes**. Eight orientations are evaluated at runtime by GLSL rotation. This preserves the existing 160 full-body view/pose choices.
- 23 author-defined static source volumes from the v14/v16/v17 generator scripts, retaining their original object IDs.
- A total of 43 physically coherent volume sources produce two 8×8 tile atlases each (RGBA + 3D outward normal map); each atlas has 64 layers × 48×48 pixels.
- 183 out of the 193 image-set names use these 43 volume sources; remaining 10 names retain the old approved imagery, including butterfly animation.
- `build_v18_gpu_atlases.py` uses `numpy`, `scipy.ndimage.gaussian_filter`, and `Pillow` at **build time**. `gpu_v18_renderer.js` uses **native WebGL2/GLSL ES 3.00**, depth testing, instanced source-volume horizontal slices, GPU directional diffuse/specular shading and image-based sun filmic pass; no CDN or runtime WASM dependency. Old source data and previous actor frames are retained.
- GPU path uses ONE existing renderRoyal requestAnimationFrame; it never starts a second loop. On WebGL2 absence or context-loss, display original 2.5D art and keep native-world toggle, movement and original blocks untouched.

## Build

```
python skills/blockwild-evolution/scripts/build_v18_gpu_atlases.py --out-dir build/blockwild_gpu18
python skills/blockwild-evolution/scripts/assemble_v18.py \
  BLOCKWILD_v17_LIVING_LIGHT_SPRITE_STACKING_OFFLINE.html \
  BLOCKWILD_v18_WEBGL2_TRUE_VOLUMES_OFFLINE.html \
  --assets build/blockwild_gpu18/gpu_volumes.json
```

Do not commit PNG atlas files or original BLOCKWILD Unity archives to the skill repository. The game itself is a single generated HTML. In headless Chromium without WebGL2, fallback was rendered in 390×844 and 844×390 with 193/193 assets loaded and zero JS exceptions. Shader compilation, actual GPU frames, mobile performance, eight-yaw visual parity, original Unity model extraction and a subjective % of visual quality remain **unverified**. `183/193 = 94.8%` measures representation coverage only; it must never be called an improvement in beauty. Validate under real WebGL2 before claiming final GPU visual success.

## Dependencies and coordination

1. `Godot/Unity → HTML` remains the source authority; original Unity textures/models have not been recovered.
2. `Hero Animator` supplies source-volume poses and stable identity; no random character replacement.
3. `META GAME FUSION` requires real transparent layer volume, depth test, texture sampling and normal map.
4. `Voxel Atmosphere Engine / Game Style Forge` supplies a single compatible lighting/film-pass aesthetic; no competing render loop.
5. `Skill Nexus` owns routing; `BLOCKWILD Visual Benchmark`/Playwright/OpenCV compares matched screenshots without inventing artistic fidelity.

Next greatest visual improvement: recover original authorized Unity model meshes and texture atlases with independently installed **UnityPy/AssetRipper** (license and version gate); then sculpt and repaint selected hero, trees and architecture in Blender with UV/PBR normal-albedo/roughness, bake high-fidelity 3D volumes for the exact same animation IDs; compare matched real WebGL2 screenshots and FPS.
