# PyMeshLab CPU → Blender → Instant Meshes/Rigger

Official https://github.com/cnr-isti-vclab/PyMeshLab
- Source commit: `9c30334547750bcbe7126278b16739349643d04b`
- Wheel: `pymeshlab==2025.7.post1`, release published 2026-01-30.
- Source license: GPL-3.0; keep dependency separate.
- CUDA/GPU: not required. Native wheel may need compatible C++ runtime/OS libraries.

## Data flow

1. Receive unanimated `.blend` with `MONSTER_RIG` or standalone source meshes.
2. Before skinning, pass only exact eligible triangle geometry to external PyMeshLab CPU Python.
3. In PyMeshLab run `meshing_remove_duplicate_vertices`, `meshing_remove_duplicate_faces`, `meshing_remove_null_faces`, `meshing_remove_unreferenced_vertices`. No erosion, remeshing, smoothing or unsupervised sculpting.
4. Verify bounds, index validity and face count in worker. Blender bridge additionally rejects objects with skin weights, any armature/other modifier, parent armature, UVs, vertex colors, shape keys, custom attributes, multiple materials, mixed face shading or references. This prevents losing animation/material data.
5. Save new `monster_cpu_pymeshlab.blend` and a compact JSON of eligible/rejected meshes; never overwrite the input `.blend`.
6. Run pre-existing `cpu_skinning_blender.py`, shape-key deformation and optional Open Mocap/Rigger. Optional Instant Meshes later retopologizes weighted models with attribute transfer.

If the CPU build has already been rigged, its meshes are intentionally **not cleaned**. This is expected safety behavior. On new unrigged imported meshes, the cleanup can change topology and subsequently the skinning stage attaches them to the existing rig.

## Invocation

`python scripts/build_cpu_only.py --blender blender --input-blend source.blend --pymeshlab-clean-static`

`python scripts/build_cpu_only.py --blender blender --input-blend source.blend --pymeshlab-audit`

Install manually using a Python environment with `python scripts/download_pymeshlab.py --install`; original PyMeshLab source clone optional via `--clone-source /work/PyMeshLab`.

Do not claim a full upstream download or real successful Blender run without obtaining the dependency and executing it.
