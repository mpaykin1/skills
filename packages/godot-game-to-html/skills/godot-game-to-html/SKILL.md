---
name: godot-game-to-html
description: >
  Original Godot/Unity source to native playable WebGL plus the most source-authentic standalone HTML visual scene possible. Sprite-stacking FIRST using independent original GLB scene mesh nodes and genuine transparent voxel slice volumes. Retains Godot, GDRETools, Unity Editor, AssetRipper, UnityPy, ILSpy/Cpp2IL, UnityGLTF, Three.js/PixiJS, KTX2/Basis, xatlas/Blender/OIDN/OpenImageIO, glTF validation and Playwright/Pixelmatch.
---

# Godot + Unity → Autonomous HTML — META GAMES 1.18

## Fundamental rule

Preserve real Godot/Unity gameplay, original GDScript/C#, physics/colliders, source geometry, rig identity, shaders, camera, UI, audio, game interactions, sound and weather. A native original-engine WebGL build is the **only default faithful playable output**. A standalone 3D/2D viewer is not a game. Never substitute original characters/models with invented primitives. All optimization and sprite stacking is on separately retained derivatives; source files are immutable. Never change protected `meta6` or reference games.

## New sprite stacking priority: maximize valid source geometry

1. For an **original static GLB scene**, default to `skills/sprite-stacking-priority/scripts/stack_scene_to_html.py ORIGINAL.glb --out OUTPUT`. Each genuine original mesh node and its transform becomes an independent voxel-sampled RGBA slice stack; unlike an all-in-one stack, doors/gates/wheels/props are available as separate authored objects. No fake depth from still photos. If original glTF has skinned/animated characters, retain their original GLB animation until independently authorized full-body volumetric poses exist.
2. For an **authorized Unity source project**, the same command first uses retained Khronos UnityGLTF to export actual scene GLBs, then packs each static scene's nodes as separate original stacks. It does **not** replace Unity gameplay. For already approved Grunge Horror `stack.json` or a scene JSON of genuine independent PNG slices, use this same command. `--assets-only` extracts original node stacks and scene JSON without trying to build HTML.
3. Existing `universal_game_to_html.py --mode stacking` and `--mode visual` (stack-first; mesh-visual fallback) remain valid for original single GLBs, approved stacks and Godot/Unity workflows; new scene-level script is preferred for composite architecture/mechanisms. Existing `stack_to_html.py` and `stack_from_glb.py` are still used internally, not duplicated.
4. The Three.js WebGL2 Data3DTexture + ray DDA renderer now writes correct first voxel surface depth, checks GPU `MAX_3D_TEXTURE_SIZE`, offers authored-color output or reversible relief-light mode and 360° view/zoom. Full-pose sequence playback is **manual by default**, so heroes do not attack or move without input. Mobile viewport responsive. Do not call this visually faithful until browser comparison passes.
5. Separate static parts may be moved/rotated *rigidly* later by original Godot/Unity/Rapier gameplay state; stack voxel meshes themselves are not collision systems. Original transparent/fog/refractive/VFX shaders and source-dependent animation remain in native renderer when faithful volume representation is unavailable. Missing source geometry must not be invented or omitted silently.

See `skills/sprite-stacking-scene-parts/SKILL.md` and `skills/sprite-stacking-priority/references/SCENE_PARTS.md` for exact commands and limits. Use `Sprite Stacking Grunge Horror`, `Meta Game Fusion`, `Hero Animator`, `Blender Model Animation Enhancer`, `Game Style Forge`, and `Skill Nexus` under their existing provenance/identity rules. No new competing engine or extra physics loop.

## All original routes remain enabled

- **Godot source** (`project.godot`) → `scripts/universal_game_to_html.py SOURCE --out OUT --mode web` → original Godot 4 native Web export. Matching Godot Web templates, temporary Compatibility profile in a COPY only, unchanged GDScript game behavior where browser-compatible. Original WebGL is authoritative, Forward+ effects/volumetric fog may differ. `--mode single` uses original experimental packer and may not run via `file://`.
- **Godot packaged source**: authorized PCK/EXE/APK → GDRETools `recover_godot.py` → original Web export where compatible. Do not claim unsupported C#/.NET/GDExtension or Godot 2/3 Web conversion.
- **Unity source** → original Unity Editor WebGL player via `unity_to_web.py` (licensed separately; not bundled), plus optional UnityGLTF scene GLB. This is playable original code when compatible. Single-file packer is experimental.
- **Unity compiled**: authorized AssetRipper + UnityPy recover original resources, ILSpy handles supported Mono DLL, Cpp2IL plus ILSpy may recover approximate IL2CPP C#. Recovered code/assets are **NOT** automatically a runnable Unity game; missing scripts/physics/AI must be reconstructed explicitly, not fabricated in viewers.
- **Original GLB visual mode** → Three.js GLTFLoader/Meshopt/Basis Universal KTX2 optional offline HTML. **2D original source frames** → PixiJS original-art 2D HTML. Never extrude a lone hero PNG into allegedly full 360° 3D.
- **Optimization**: xatlas UV2 and Blender CPU AO only on static original derivatives; optional OIDN on baked AO only, OpenImageIO for HDR lightmap color management, Oxipng lossless PNG, glTF-Transform/gltfpack opt-in meshes, FFmpeg opt-in audio, Khronos KTX-Software candidate textures with original PNG fallback and validated Three.js Basis decoder. No automatic loss of original albedo/normal map/shader.
- **Quality**: official Khronos glTF Validator checks schemas and scene node/animation identity; Playwright captures original and candidate WebGL frames and Pixelmatch compares synchronized camera/time/exposure. Dynamic weather/fog can make comparisons inconclusive. No invented visual preservation percentages.

## Runtime and rights

Only authored/rights-approved original game files, stable SHA256 provenance, unchanged animation/camera identities. Source art and author rights must persist. WebGL2 is required for 3D stack textures; fallback to actual original native WebGL/GLB/Pixi when absent, not to approximate Canvas cubes. No third-party executables are vendored in this plugin. Scene viewer ≠ full Godot/Unity game. Do not claim public deployment without actual URL. No unsolicited reports, handoff, test/evidence artifacts.
