# xatlas → UV2 → optional Blender Cycles CPU AO

## Upstream / license

- xatlas C++ MIT: https://github.com/jpcy/xatlas
- xatlas Python MIT (pinned release 0.0.11): https://github.com/mworchel/xatlas-python
- Blender GPL: https://github.com/blender/blender
- Blender AO baking docs: https://docs.blender.org/manual/en/latest/render/cycles/baking.html

## Roles and relationship to existing tools

- **Godot Engine** and **Unity Editor** retain original scenes, scripts, animations, material graph and renderer. The normal Web export stays the default.
- **GDRETools**, **AssetRipper** and **UnityPy** recover actual source assets, not substitute procedural art.
- **xatlas** creates a second UV map (UV2) for static, triangulated meshes; unlike a main UV unwrap it must not touch UV0/albedo/normal maps or vertices. The worker translates xatlas remap indices to Blender's per-face-corner UV2.
- **Blender** optionally bakes ambient occlusion on CPU into *separate PNG sidecars*. It does not overwrite original materials or automatically replace runtime lights. Only opt-in `--bake-ao` turns on this expensive stage.
- **oxipng** losslessly recompresses baked AO PNGs in a copy; **glTF-Transform** and **gltfpack/meshoptimizer** can optimize *derivative* models after UV2 is confirmed; **FFmpeg** stays independent for audio. Do not run destructive glTF optimizers before UV2 without preserving UV1/AO material bindings.
- Other META GAMES skill GLB outputs (`blender-model-animation-enhancer`, `meta-game-fusion`, `game-style-forge`, `voxel-atmosphere-engine`) can enter the same UV2 stage; keep source file, material names, scene transforms and object identity. Dynamic rigged heroes are **excluded** from AO baking.

## Installation (CPU only, no vendored binaries)

Requires Blender installed from official source. In Blender's Python runtime install `xatlas==0.0.11` from PyPI or the above GitHub source; no auto-download without permission. Command line entrypoint:

```bash
python skills/godot-game-to-html/scripts/xatlas_lightmaps.py original_static_scene.glb --out ./atlas
python skills/godot-game-to-html/scripts/xatlas_lightmaps.py original_static_scene.glb --out ./atlas --bake-ao --size 512 --samples 24
python skills/godot-game-to-html/scripts/xatlas_lightmaps.py original_static_scene.glb --out ./atlas --export-glb
```

Outputs: `atlas/uv2-source.blend` containing non-destructive UV2 source; `atlas/atlas-manifest.json` (per mesh, preserved UV0, skipped objects); with `--bake-ao`, `atlas/ao/*_AO.png` as sidecars; with `--export-glb`, experimental `atlas/uv2-derivative.glb`. The original `.glb` is never modified. Source projects are not modified.

## Fidelity constraints

1. No existing UV2 is overwritten. Skip skinned, animated, shape-key, non-triangulated, modifier-driven meshes and meshes missing original UV0.
2. Mesh positions/topology, original UV0, materials and animation data are preserved in `.blend`. Per-face-corner xatlas UV mapping supports chart seams without splitting original geometry.
3. Blender glTF re-export may change exact binary representation or prune unused UV channels; derivative GLB cannot be presumed equivalent or suitable to replace imported Godot/Unity assets without inspection.
4. AO should apply only to static scenery, after explicit review. It must not be multiplied blindly into baseColor on dynamic characters or mixed into fog/light scattering.
5. Existing rendering differences between Godot Forward+ and Compatibility/WebGL 2 remain. xatlas alone cannot recreate volumetric fog, snow shaders, post FX or guarantee any measured visual similarity.
6. Do not call the feature successfully integrated into game imagery without examining rendered before/after in the target browser. No fake pass.
7. If Blender/xatlas are absent, leave the original export intact and report stage unavailable, never replace textures or models with primitives.
