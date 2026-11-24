---
name: godot-game-to-html
description: >
  Original Godot/Unity games into native playable WebGL plus offline visual 3D HTML. Mandatory sprite-stacking-first for the maximum feasible original static scene graphics: true horizontal transparent PNG volume slices from GLB, compatible with Sprite Stacking Grunge Horror, CPU trimesh/SciPy/Pillow and Three.js WebGL2 360-degree DDA renderer. Keep original native game logic, GDRETools, AssetRipper, UnityPy, ILSpy, Cpp2IL, UnityGLTF, PixiJS, KTX2/Basis, validators, lightmap pipeline and safety rules intact.
---

# Godot + Unity → Autonomous HTML — META GAMES 1.17 — SPRITE STACKING FIRST

## Non-negotiable

**MAXIMIZE genuine sprite stacking as the primary visual representation for all compatible static 3D objects and surroundings.** Not merely a menu option: every new scene conversion first attempts true stack-based objects, then keeps original GLB/engine rendering for unsupported portions. The original Godot/Unity executable project and native WebGL build are still the only source of actual playable physics, GDScript/C# gameplay, AI, interaction and input. A visual-only Three.js/PixiJS/stacking HTML is never mislabelled as the full game. Keep original character identity, original mesh/textures, camera/animation/audio/UI, weather, fog, material and shaders; never rewrite, erase or replace them with procedurally invented props. Do not modify protected `meta6` or reference games.

## Four visual layers — stacking-max coverage

- **Deep background:** original distant static structures, silhouettes, city ruins, rock formations → actual sprite stacking volumes when source geometry exists; original skybox, distant fog and lighting maintained in separate engine layer.
- **Middleground:** nearly every static 3D architectural piece, gate, bridge, tree trunk, vehicle chassis, furniture, machinery and props → original authored GLB → horizontal transparent RGBA slices; animate doors, wheels and platforms using independent *rigid* stack parts, with game physics/colliders still authoritative.
- **Foreground:** rubble, grass/foliage shells, stones, debris, barriers → stack from original volume or original shell triangles; preserve holes, transparency semantics and material identity. Complex translucent surfaces retain source renderer when volume cannot represent them faithfully.
- **Screen + dynamic FX:** UI, rain, particles, fog, bloom, glitch, lens grime, soundtrack → retain existing native/GLSL/PixiFX, not fake voxel surfaces.

**Characters, animated creatures, weapons:** from the author's **full, individually approved stack volume for each entire pose/frame**, no single-image extrusion, no warp, no morph and no identity swap. Keep one consistent pivot and identical full-volume dimensions for all animation frames. If those authored pose volumes are unavailable, use original GLB skinning and native game animations, NOT an artificial static stack or generated action. Users may use their `sprite-stacking-grunge` authoring skill to create the actual slices; this plugin imports the same `stack.json` verbatim.

## Canonical CLI and priority

```bash
# Explicit true sprite stacking of original static GLB or Unity source project:
python scripts/universal_game_to_html.py ORIGINAL.glb --out OUT --mode stacking
# Existing 3D visual route: sprite stacking FIRST; automatically falls back if ineligible:
python scripts/universal_game_to_html.py ORIGINAL.glb --out OUT --mode visual
# Explicit previous original GLB viewer when user needs native mesh/shaders:
python scripts/universal_game_to_html.py ORIGINAL.glb --out OUT --mode visual --mesh-visual
# Full original gameplay (source project): never substitute visual previews:
python scripts/universal_game_to_html.py ORIGINAL_UNITY_OR_GODOT_PROJECT --out OUT --mode web
```

`--mode stacking` supports `.glb`, original Unity project through Khronos UnityGLTF, a folder of original GLBs, `stack.json` or author-defined multi-object scene JSON. For actual pre-authored PNG stacks, route directly to `skills/sprite-stacking-priority/scripts/stack_to_html.py /approved/stack.json --out output/sprite.html` or through the canonical CLI. Use `--stack-xy` and `--stack-z` for volume size, `--stack-closed-only` to reject thin shell geometry, `--no-install` for offline cache. With `--ktx-manifest`, keep existing KTX2/Basis original GLB viewer route rather than falsely claiming a textured stack bake. New 2.5D/3D output is a **visual scene**, not a reimplemented original engine.

`skills/sprite-stacking-priority/SKILL.md` is mandatory for visuals. `stack_from_glb.py` uses MIT trimesh for voxelizing **source triangles**, SciPy closest-surface UV sampling and Pillow for true bottom-to-top RGBA slices. It rejects source geometry that would force fabricated colors or unsupported animation. `stack_to_html.py` packages actual PNG voxels and original stable coordinates, enforces 128MiB scene volume cap and uses pinned local Three.js 0.187.0, esbuild 0.25.5, Data3DTexture and GLSL DDA to show correct visibility from full azimuth and pitch; a camera facing edge-on is still an actual volume, not a flat billboard. It can animate complete pose stacks by swapping volumes; no automatic attack or AI. All original sources remain unchanged. Missing dependencies fail the optional stage openly.

## Godot original runtime: always the playable route

- Complete original `project.godot` → `game_to_html.py` → `godot_to_web.py` with version-matched editor + export templates, Web preset and Compatibility rendering applied only in a working copy. Preserve GDScript and original 3D physics. `--mode single` packages original Godot Web output with `pack_single_html.py` where possible; `file://` remains experimental. Godot 2/3, C# and GDExtension compatibility is not assured.
- Authorized `.pck`/Godot executable without sources → GDRETools (`install_gdretools.py`, `recover_godot.py`) for original scene/assets recovery first. No claim that recovered encrypted/missing code magically yields playable WebGL. Sprite stacking may use original recovered GLB assets as optional visual copies; do not replace native Godot game logic.

## Unity original runtime and compiled recovery

- Complete original Unity project (`Assets`, `ProjectSettings/ProjectVersion.txt`) → matching installed Unity Editor with WebGL build module → `unity_to_web.py`. Original scenes, C#, colliders, renderer state and gameplay stay authoritative. `pack_unity_webgl.py` handles **experimental** single HTML. `--mode scenes` or `--mode web --export-glb` invokes `export_unity_glb.py` and Khronos UnityGLTF 2.25.0, exports original GLB scene/animation for visual stacking or native Three.js rendering. Skinned or heavily shader-specific models remain in GLB where slicing loses source fidelity.
- Authorized compiled Unity resource folders and `.assets`/`.bundle` → AssetRipper 2.0 recovers scene/resource graph, UnityPy 1.25.4 exports actual PNG/OBJ/WAV/fonts/serialized data and provenance (`--mode recover --extractor auto|assetripper|unitypy|both`). Do not hallucinate restoration of missing game code.
- `--mode code` or `--mode recover --with-csharp` handles ILSpyCmd 11.2 reconstruction of Unity **Mono** managed DLLs, or Cpp2IL approximate DLL recovery for IL2CPP followed by ILSpy when possible. Obfuscation, IL2CPP native logic, GUID links and source fidelity may be missing. Do not auto-port gameplay or run unknown game binaries; use only authorized files.

## Remaining compatible modules: keep all

- **Original GLB viewer:** `skills/three-glb-visual-runtime/scripts/three_glb_to_html.py`; Three.js 0.187.0, GLTFLoader, OrbitControls and MeshoptDecoder. It preserves original textured meshes, skinning and GLB animations where suitable and does not recreate C# game logic.
- **Original PNG/2D:** `skills/pixi-original-sprites/scripts/pixi_sprites_to_html.py` via canonical `--mode sprites`, PixiJS 8.23.0, original full RGBA animation and manifest provenance; never duplicate identical frames and call them motion.
- **Khronos KTX-Software** UASTC 4×4 + validation; **Basis Universal** offline KTX2 WebAssembly decoder inside the Three.js viewer, retaining original PNG fallback. Requires explicit candidate selection, correct sRGB/data color space, and browser visual matching; KTX2 encoding is lossy.
- **Static AO pipeline:** approved static GLB → xatlas UV2 (never overwrite UV0) → Blender Cycles CPU AO as separate PNG → Intel OIDN CPU optional denoising of AO only → OpenImageIO explicit HDR/EXR color management and AO inspection → oxipng lossless; glTF-Transform/gltfpack optional separate optimized GLB, FFmpeg for independent audio. No shader replacement or hero mesh modification without verified opt-in.
- **Integrity:** official Khronos glTF Validator before original GLB packaging or candidate comparison; Playwright Chromium captures matched actual browser views; Pixelmatch compares pixels. Dynamic blizzard/fog must be synchronized for meaningful parity. A low pixel-difference does not prove gameplay equivalence. Broken/unavailable software means stop or fallback to original source, never claim visually restored content.
- **Game interoperability:** `hero-animator` author-approved frames/identity and Rapier colliders remain authoritative for animated hero physics; `meta-game-fusion`, `game-style-forge`, `casual-game-studio`, and `blender-model-animation-enhancer` can consume the verified stack.json volume sidecars and compose living worlds. Never build competing fake versions of an authored game or use a single photo to fabricate full 360 geometry.

## Result and rights

Render only authorized original art and code, keep third-party licenses and source hash. Source GLB/WebGL is never overwritten; separate stack PNGs, `stack.json`, and optional standalone offline HTML are derivatives. Quality gate must compare to the original at matching camera and timing before accepting a reconstruction. WebGL2 with 3D textures required by stack viewer; Android/iOS/browser support varies. Single-file visual HTML may still require a compatible browser; full autonomous Godot/Unity game remains a separate engine export. No invented playable URL, no reports/tests/handoff/evidence unless explicitly requested.
