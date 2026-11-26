# Trimesh CPU — structural inspection of monster geometry (v1.7.0)

Official upstream: https://github.com/mikedh/trimesh ; MIT License.
Pinned stable version: **4.11.1**, official tag commit `934ea6c3b70341caf41849552b623b78113f4ea7`. Latest upstream was 5.2.2 as of 2026-11-23, but 4.11.1 is already installed in our build environment and can be executed on CPU. This ZIP does **not** bundle third-party library source or an external binary; use the real PyPI wheel `trimesh==4.11.1` and `numpy`.

## Cooperation with existing pipeline

`Blender + Rigger/Open Mocap → PyMeshLab (optional CPU repair of eligible static meshes) → xatlas UV + Pillow PBR → Trimesh CPU structural audit → glTF-Transform → meshoptimizer/gltfpack → Khronos Validator`.

- Trimesh loads the **final uncompressed GLB read-only**, analyzes unique triangular meshes and their rest-pose geometry, validates finite coordinates/face indices, detects collapsed triangles, non-manifold edges, inconsistent triangle winding, and reports open boundaries (which may be intentional on muscles, skin sheets, or clothing).
- The source GLB and .blend remain byte-for-byte unchanged; Trimesh is used for inspection, **not** a replacement GLB exporter. Existing bones, weights, animation clips, UVs, PBR and muscle morph targets are not rewritten.
- Strict mode rejects degenerate faces, non-manifold edges, and inconsistent winding. Open boundaries remain warnings because some muscle surfaces are deliberately open.
- PyMeshLab can subsequently repair eligible **static unrigged untextured** meshes. For skinned assets do NOT invoke destructive repair just to eliminate warnings.
- Khronos Validator remains responsible for glTF schema, buffer accessors, skin and animation format validity. Trimesh does not validate animation playback, joint deformation, or dynamic muscle collisions. This is a rest-pose topology check only.

## Commands (CPU only)

```sh
python -m pip install 'trimesh==4.11.1' numpy
python scripts/trimesh_cpu_guard.py --input monster.glb
python scripts/trimesh_cpu_guard.py --input monster.glb --strict
python scripts/build_with_anatomy.py --blender blender --trimesh-audit
```

For an existing character:

```sh
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend your-monster.blend --trimesh-audit
```

Use `--trimesh-python /path/to/python` if Trimesh is installed outside Blender Python. The audit runs **after** UV/PBR changes but **before** glTF-Transform/meshoptimizer compression. A meshopt/Draco-compressed GLB is rejected with a descriptive error and must be audited pre-compression.

Without installed Trimesh or a valid GLB, this stage fails openly; no fake metrics. On large meshes, Trimesh's edge topology analysis may take significant CPU time and memory. Dependency and execution status must not be overstated.
