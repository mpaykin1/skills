---
name: gltf-asset-guard
description: >
  Official Khronos glTF Validator 2.0.0-dev.3.10 for original and optimized GLB;
  preserve scene, texture, materials, animation IDs. Offline Basis Universal support
  only when the Three.js KTX2Loader is actually bundled.
---

# Khronos glTF Validator — enforced model integrity

The pinned official `gltf-validator` validates GLB 2.0 before the original GLB Three visual HTML builder runs. It must reject invalid GLB and require self-contained resources. No silent disabling of validation is permitted.

- `node validate-glb.mjs original.glb --browser-bridge` rejects unsupported `KHR_texture_basisu`, Draco, `KHR_animation_pointer`, `KHR_interactivity`, `KHR_materials_variants`.
- `node validate-glb.mjs source.glb --browser-bridge --offline-basis` authorizes **only `KHR_texture_basisu`**, for the actual single-file HTML pipeline with Three.js KTX2Loader and locally bundled Basis Universal JS/WASM. Draco/animation pointer/interactivity/variants remain blocked. This is NOT permitted when the offline decoder is absent.
- `node validate-glb.mjs source.glb --compare candidate.glb` checks both with the official validator and refuses lost source scene/node/material/animation/skin/camera names or all texture/image data. It is structural integrity, **not** proof of identical appearance.
- Validated KTX2 candidates require Khronos KTX-Software `ktx validate --gltf-basisu`; only these are linked into GLB using exact original PNG byte hashes while retaining fallback source.
- Godot/Unity native WebGL remains the authoritative playable build. The 3D HTML viewer is not a full game. Compare actual browser frames with Playwright/Pixelmatch before approval. Never modify originals.

Source: https://github.com/KhronosGroup/glTF-Validator (Apache-2.0). The module is installed locally only at build time.
