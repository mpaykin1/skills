# Manifold3D CPU — static sculpt union bridge

[Manifold](https://github.com/elalish/manifold) `v3.5.5` (Apache-2.0) is a robust CPU constructive-solid-geometry (CSG) backend; bindings `manifold3d` are official and work without GPU. Use it *after* static inspection/optional PyMeshLab cleaning and *before* Blender skinning, xatlas UV mapping and Pillow PBR. It complements Trimesh: Trimesh checks inputs/output; Manifold performs the actual union.

## Installation and use

`python scripts/install_manifold3d_cpu.py --install` installs the official CPU package into an external Python environment. Launch the standard Blender CPU pipeline with `--manifold-cpu` and, where auto-detection does not find named/tagged meshes, `--manifold-objects MUSCLE_CHEST_L,MUSCLE_CHEST_R`.

```sh
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend creature.blend --manifold-cpu --manifold-objects MUSCLE_CHEST_L,MUSCLE_CHEST_R
```

Direct worker for independently supplied mesh-data JSON (2..24 closed meshes):

```sh
python scripts/manifold3d_cpu_worker.py --input source-solids.json --output fused-guide.json
```

The Blender bridge accepts read-only mesh rest snapshots, even for already rigged or textured approved models. The bridge does not apply modifiers or transfer materials, UVs, weights or shape keys into the union. UV-seam stitching, material transport, reskinning and muscle shape-key deformation *cannot be preserved automatically* over changed topology; therefore the Boolean union is a visible `MANIFOLD_SCULPT_REFERENCE` wireframe in a **new** `.blend`. It is tagged `non_exportable_reference` and excluded from final GLB. The original body and muscles remain authoritative. If user wants the Boolean union as the **actual game mesh**, they must separately approve the new topology and redo weights, UVs and morphs; do not silently substitute the character.

Fail closed for open/inverted/degenerate geometry, insufficient or missing inputs, missing real `manifold3d`, no Blender, or unsafe data. No fake Python union replacement. No network inference, GPU, CUDA, or cloud dependency.

This integration has been packaged as native-code adapters; Blender's actual runtime is not available here and the upstream wheel was not downloaded due network restrictions. Do not claim an executed Blender Boolean without observing it.
