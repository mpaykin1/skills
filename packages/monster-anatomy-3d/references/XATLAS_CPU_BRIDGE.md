# xatlas / Monster Anatomy 3D — CPU-only UV atlas integration (v1.4)

Original xatlas: https://github.com/jpcy/xatlas (MIT).
Python binding: https://github.com/mworchel/xatlas-python (MIT), `xatlas==0.0.11`.

## How this strengthens the pipeline

1. PyMeshLab safely cleans eligible static geometry.
2. Instant Meshes optionally prepares a lower-density game mesh, transferring
   existing material/skin/morph data under its own fail-closed guard.
3. Blender builds or preserves `MONSTER_RIG`, muscle meshes, morph shapes and
   existing NLA animation; Rigger / Open Mocap add new clips.
4. xatlas then unwraps only *monster meshes lacking UVs*. All C++ computation
   runs on CPU in an external Python process. Output UVs are assigned to
   Blender polygon **loops**, not split vertices. Therefore vertex indices,
   skin weights, bone names, animation curves and morph shape-key data are not
   modified. Existing UV maps or image-textured models are untouched.
5. Blender creates a separate `.blend` and animated `.glb`, structurally
   compared with source GLB for clip names/channels, bones, morph target counts,
   materials and mesh counts. glTF-Transform and Khronos validation run after.

## Use

Install once with Python CPU environment:

```bash
python scripts/install_xatlas_cpu.py --install
```

Run with the default CPU pipeline:

```bash
python scripts/build_with_anatomy.py --blender blender --xatlas-uv
```

If already installed in a separate environment:

```bash
python scripts/build_with_anatomy.py --blender blender --xatlas-uv \
  --xatlas-python /path/to/python
```

Compatible with `--gltf-optimize --gltf-validate` after external Node tools
are installed. The source is never overwritten. CPU worker is
`scripts/xatlas_cpu_worker.py`, Blender bridge is
`scripts/xatlas_blender_bridge.py`.

## Conservative restrictions

- No remeshing, topology mutation, material creation, procedural textures or
  texture baking. UVs **enable** future PBR texture authoring but do not paint
  diffuse/normal/roughness maps automatically.
- Meshes already carrying any UV map, shared Mesh datablocks, reference-only
  objects and meshes with image nodes but no UV are skipped.
- If xatlas introduces an internal seam in the middle of an original n-gon
  and per-loop UV transfer is impossible, that mesh is skipped; this does not
  risk skin or morph data.
- When ALL candidate meshes are ineligible, fail explicitly, rather than
  claiming a changed model. `--xatlas-allow-noop` permits intentional no-op.
- Structural checks don't prove identical rendered appearance. Author review
  inside the game is necessary; no GPU rendering is performed in the skill.
- Upstream xatlas wheel and Blender are not bundled: installing them requires
  external system dependencies and may require internet. CPU-only capability
  does not imply Blender is installed in ChatGPT runtime.
