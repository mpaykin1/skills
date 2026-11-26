# Pillow 12.3.0: CPU PBR texture baking after xatlas (fourteenth source)

Sources: [Pillow](https://github.com/python-pillow/Pillow) (MIT-CMU),
[xatlas](https://github.com/jpcy/xatlas) (MIT),
[PyMeshLab](https://github.com/cnr-isti-vclab/PyMeshLab) (GPL-3.0).

## Real integration

`Blender / Rigger / Open Mocap → optional PyMeshLab static cleanup → optional
Instant Meshes → xatlas per-loop UV atlas → Pillow CPU texture rasterizer →
Blender PBR shader + packed PNG → GLB → glTF-Transform → Khronos Validator`.

Pillow generates **two genuine images** per eligible material: sRGB albedo PNG
and non-color grayscale roughness PNG. The base color is taken from the existing
Principled BSDF, converted linear→sRGB correctly. Surface-normal deviation is
sampled on the *existing resting mesh* and interpolated over its actual UV
triangles to accentuate sculpted anatomical creases. No tiling, noise pattern,
random dirt, or fake detail is introduced. `wetness` optionally reduces
roughness and enhances a slick, damp monster look without changing geometry.
No actual physical AO, microscopic normals or 3D hair is inferred.

The Blender bridge uses a separate CPU-Python Pillow process (never imports
Pillow into Blender), copies only simple, untextured Principled materials and
leaves ALL existing image/procedural materials untouched. It packs PNG images
into the new `.blend` and embeds them in the exported `.glb`. It preserves mesh
vertices/UVs, vertex group weights, shape keys, armature bones, named clips,
and morph target counts by comparing before/after fingerprints/signatures.

## One command

```bash
python scripts/install_pillow_cpu.py --install
python scripts/install_xatlas_cpu.py --install
python scripts/build_cpu_only.py --blender blender --output-dir build/pbr-cpu \
  --xatlas-uv --pbr-cpu --pbr-size 512 --pbr-wetness 0.35 \
  --gltf-optimize --gltf-validate
```

The full anatomy pipeline also supports `--pbr-cpu`, `--pbr-size`,
`--pbr-wetness`, and `--pbr-python` **after** `--xatlas-uv`.

For already prepared `.blend` with `XATLAS_CPU` UVs:

```bash
blender --background --factory-startup --python-exit-code 3 \
  --python scripts/pillow_pbr_blender.py -- \
  --blend monster_xatlas_uv.blend --source-glb monster_xatlas_uv.glb \
  --output-blend monster_pbr.blend --output-glb monster_pbr.glb \
  --texture-dir pbr_textures/ --python-bin python --size 512 --wetness 0.35
```

A worker can be exercised without Blender using valid UV triangle JSON.

## Hard limits

- Requires installed official Pillow==12.3.0 (CPU). Blender itself still
  required for live material wiring and GLB export. Cannot assert tested
  Blender or Three.js final look without actually running those runtimes.
- Does not overwrite existing artist images, node graphs, original .blend or
  original .glb. It does not invent a texture layout from an un-UV'd mesh.
- Only `XATLAS_CPU` UV sets are used by default. If xatlas cannot unwrap,
  skip or stop rather than contaminate another UV set.
- If an output file exists the stage stops. If the official Pillow is missing,
  stage stops. If clips/skins/morphs differ, the new scene and GLB are removed.
- Geometric microdetail is based only on actual mesh face normals. Low-poly
  source anatomy will remain low-poly; no false realistic sculpt guarantee.
