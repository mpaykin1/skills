# SciPy CPU skin-weight diffusion — v1.9.0

Official open source: https://github.com/scipy/scipy, tag **v1.17.0** (BSD-3-Clause). CPU-based; package is not vendored. Uses `scipy.sparse` and `numpy`, in a **separate Python process from Blender's bundled bpy**. No CUDA, GPU, or neural checkpoints.

## Purpose and place in the existing pipeline

Manifold3D creates an *independent sculpt reference only* → PyMeshLab fixes eligible unweighted static meshes → Blender's real Bone Heat (or CPU proximity fallback) binds **new, unweighted** muscles to `MONSTER_RIG` → **SciPy diffuses those new per-vertex bone weights over mesh-connected edges** → Blender morph/NLA animation and Rigger/Open Mocap motion → xatlas UV → Pillow PBR → glTF-Transform/meshoptimizer optimization → Khronos validation.

This is **not** a replacement for Blender rigging, a neural auto-rigger, or anatomical muscle simulation. It only reduces sharp transitions in freshly assigned skin weights. It never creates new bones or replaces approved animated meshes.

## One command

```sh
python -m pip install 'scipy==1.17.0' 'numpy>=2.3,<2.5'
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend /path/monster.blend --scipy-skin-smooth
```

The same optional `--scipy-skin-smooth` flag works with `scripts/build_cpu_only.py`. `--scipy-python` selects an interpreter with SciPy already installed, `--scipy-iterations 3` and `--scipy-strength 0.35` control the filter. Also supports standalone Blender bridge invocation:

```sh
blender --background --python scripts/cpu_skinning_blender.py -- \
  --blend monster.blend --output-blend monster-smoothed.blend \
  --scipy-skin-smooth --scipy-python python
```

## Hard restrictions

- Only `skin_eligible()` Blender meshes with **no preexisting vertex groups** are modified. Hand-painted weights, already skinned creature, old muscle morphs, materials, UVs, armature bones and NLA clips remain completely untouched.
- Sparse graph edges come from polygon border connectivity, not spatial proximity: coincident neighboring muscle shells do **not** blend with each other. Isolated/unweighted vertices and zero-length edges are refused rather than guessed.
- The solver preserves attachment anchors with initial maximum bone weight at least 0.995; it normalizes each vertex's weights to one, caps influence count to <=4 for glTF, and rejects NaNs, bad shape, over-budget inputs, and suspiciously large weight changes.
- The Blender bridge preserves original vertex indices and polygons and writes into **newly created** vertex groups only, in a new output `.blend`. Original mesh and shape key coordinates never change. It validates the solver results *before* modifying any groups.
- The procedural starter monster already has a skinning rig. Running on it may legitimately skip every object: `--scipy-skin-smooth` does not arbitrarily repaint approved weights. Use it when importing **new unweighted muscles or skin meshes**.
- This is a CPU-side graph filter, not bounded biharmonic weights or a pose-deformation solver. No game-performance/FPS gain is guaranteed. Evaluate the actual final muscle bending in Blender or Three.js.

Real SciPy API execution can be checked separately without Blender; this packaged runtime has **no `bpy` binary**, so end-to-end animation/export remains unverified. Missing real SciPy dependencies stop the requested stage rather than claiming success.
