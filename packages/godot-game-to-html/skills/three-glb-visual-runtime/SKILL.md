---
name: three-glb-visual-runtime
description: >
  Original Godot/Unity GLB to single offline HTML using pinned Three.js 0.187.0,
  original models/textures/animations, Khronos glTF Validator and embedded
  Basis Universal JS/WASM transcoder for KHR_texture_basisu KTX2 textures.
---

# Three.js original GLB → autonomous visual HTML (Basis Universal integrated)

This module belongs to the EXISTING Godot + Unity → Autonomous HTML plugin. Keep the original Godot/Unity WebGL game as the only authoritative playable build. GLB+Three.js is a visual scene; it does **not** automatically restore game code, input, physics, UI, AI, or authored shaders.

## Direct pipeline

1. Authorized Unity original project → native Unity WebGL for **gameplay**, optionally Khronos UnityGLTF → original GLBs. Authorized Godot project → native Godot WebGL, optionally original GLBs. AssetRipper/UnityPy/ILSpy/Cpp2IL are for source recovery, not a substitute for playable engine export.
2. **Khronos KTX-Software** produces separately validated UASTC KTX2 candidates from original approved PNGs (`ktx2-candidates.json`). The new `embed_ktx2_glb.py` only matches source PNG images in a GLB to candidate records by **byte-identical SHA-256**; it never guesses by filename. It adds `KHR_texture_basisu` and keeps the original embedded PNG as glTF fallback. This produces a *separate* derivative GLB without touching the original.
3. **NEW Basis Universal** runtime is loaded via the exact pinned `three@0.187.0` npm package, using Three `KTX2Loader`, locally embedded `basis_transcoder.js` and `basis_transcoder.wasm`, a blob LoadingManager and Web Worker. The HTML has no runtime CDN, external JS, or textures. No Basis binary is checked into this skill; its npm copy is embedded during build with its Apache 2.0 license text.
4. **Khronos glTF Validator** must run before HTML packaging. `validate-glb.mjs --browser-bridge --offline-basis` only relaxes the previously blocked `KHR_texture_basisu` *when* the verified embedded decoder is part of this pipeline. Draco, `KHR_animation_pointer`, `KHR_interactivity`, `KHR_materials_variants` remain blocked. A malformed GLB must not pass.
5. Original GLB scene graph, mesh, textures, animations and cameras render through pinned Three.js+GLTFLoader+MeshoptDecoder. `OrbitControls` supports desktop/touch. Original textures never replaced by invented textures or generic primitives; default visual lighting is clearly viewer-only. `glTF-Transform`, xatlas, OIDN, OpenImageIO, glTF Validator and Pixelmatch/Playwright are complementary optional validation/optimization stages.

## One command

```bash
# Original GLB, no KTX replacement needed:
python skills/three-glb-visual-runtime/scripts/three_glb_to_html.py original.glb --out view.html

# Connect Khronos KTX candidates by exact original PNG hash:
python skills/three-glb-visual-runtime/scripts/three_glb_to_html.py original.glb --ktx-manifest ktx2-candidates.json --out view-ktx2.html

# Unified plugin entrypoint:
python skills/godot-game-to-html/scripts/universal_game_to_html.py original.glb --out view.html --mode visual --ktx-manifest ktx2-candidates.json
```

`--no-install` requires a cached pinned Node toolchain; otherwise npm installs pinned `three`, `esbuild`, `gltf-validator` only during BUILD. Node is not required to open resulting HTML. The original WebGL game is not modified. Output existing paths are rejected unless explicit `--force` in visual bridge. No internet access is required by the *final HTML*.

## Safeguards

- KTX2 is lossy and may alter materials, transparency, or normal maps; use the existing Playwright/Pixelmatch real-browser comparison before approving visual derivatives. Original PNG fallback remains and may increase HTML filesize; GPU memory is the primary benefit, **not guaranteed smaller HTML**.
- If candidates do not match the exact PNG bytes already embedded inside original GLB, **stop**. If source GLB uses external URIs, unsupported encodings/extensions, no texture references, or Basis JS/WASM cannot be bundled, fail visibly.
- Blob worker/WASM execution depends on browser security settings, including some `file://` modes. Do not claim every target device was tested unless actually launched.
- Keep MIT/Apache license notices. Process only owned/authorized games. Never modify protected `meta6` or its reference builds.

See `references/BASIS_UNIVERSAL.md` and `references/THREE_RUNTIME.md`.
