---
name: basis-universal-offline
description: >
  Adds Binomial Basis Universal KTX2 GPU texture transcoding to the existing
  Godot + Unity → Autonomous HTML plugin using pinned Three.js KTX2Loader,
  inline WASM/worker and Khronos validated KTX2 candidates.
---

# Basis Universal → original 3D scenes in autonomous HTML

This is a **component of the existing** `godot-game-to-html` plugin, not another game converter. Prioritize original native Unity/Godot WebGL gameplay. Build visual HTML only from authorized original GLB sources; don't claim restored game logic or replace approved source models, textures, animation, or art style.

## Pipeline

- Khronos `ktx2_textures.py` produces UASTC LDR candidates from original PNG, validating each using `ktx validate --gltf-basisu`. Preserve original PNG as authoritative.
- `three-glb-visual-runtime/scripts/embed_ktx2_glb.py` matches approved KTX2 candidates by byte-identical SHA256 of PNG embedded inside original GLB. Adds `KHR_texture_basisu`, retains source PNG fallback, emits only a new derivative GLB.
- `three-glb-visual-runtime/scripts/three_glb_to_html.py` invokes the linker when `--ktx-manifest` is passed, then official Khronos glTF Validator, then Three.js 0.187 KTX2Loader + embedded Basis Universal JS/WASM + original GLB in one offline HTML. No CDN. All previous 2D PixiJS, original Unity/Godot WebGL, AssetRipper, UnityPy, ILSpy, Cpp2IL, xatlas/Blender/OIDN, Khronos Validator, Playwright/Pixelmatch are retained.
- If an original PNG hash differs, *stop*; never use filename matching or generate replacement textures. Browser WASM/Blob workers may be restricted; never assert full fidelity until actual browser test.

```
python skills/godot-game-to-html/scripts/ktx2_textures.py textures --out ktx2 --kind color
python skills/godot-game-to-html/scripts/universal_game_to_html.py scene.glb --mode visual --out scene.html --ktx-manifest ktx2/ktx2-candidates.json
```

Original native Unity/Godot export is still the playable game. This pipeline is a visual rendering tool, not automatic translation of scripts, AI, UI, game rules, or physical interactions. Full details: `../three-glb-visual-runtime/references/BASIS_UNIVERSAL.md`.
