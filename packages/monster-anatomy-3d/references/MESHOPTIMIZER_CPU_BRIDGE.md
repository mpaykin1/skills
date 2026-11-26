# meshoptimizer v1.3 + gltfpack — CPU game-GLB integration

Project: https://github.com/zeux/meshoptimizer — MIT © 2016–2026 Arseny Kapoulkine.
Release: https://github.com/zeux/meshoptimizer/releases/tag/v1.3
Pinned release commit: `9e1f07b159d3cb777f1c67ed31fc11fd117986f4`.

## How the open-source projects reinforce each other

1. **MyoGeneratorRemix + Blender + Rigger/Open Mocap** produce one consistent animated monster with mesh skinning, shape keys and NLA clips.
2. **PyMeshLab** diagnoses static meshes and **Instant Meshes** handles optional pre-export topology improvements (not on the approved rig without attribute transfer).
3. **xatlas** adds missing UVs while the bridge preserves original vertex weights and morphology; **Pillow** bakes CPU PBR color/roughness into textures.
4. **glTF-Transform** optionally removes duplicate GLB resources without replacing materials; when both tools are chosen use ONLY `--gltf-mode safe` first.
5. **meshoptimizer's official gltfpack v1.3** reorders mesh data for rendering and optionally compresses geometry (`-c`). It runs as a real external native CPU executable, not a fake optimizer. It is always an *opt-in final stage*.
6. **Khronos glTF-Validator** checks original and candidate; the original independent bridge also checks bone hierarchy, mesh/morph mappings, animation clips and channels, PBR factors, UV attributes, and original embedded image bytes. Fail closed if any protected structure changes. Unchanged original is never overwritten.

## Install CPU-only executable

```bash
python scripts/install_meshoptimizer_cpu.py --dest vendor/gltfpack-v1.3
```

The installer downloads the **official** GitHub binary matching Windows/Linux/macOS; checks the release ZIP's published SHA-256 and extracts only `gltfpack`. A previously obtained official ZIP can be used **offline** with `--archive /path/to/gltfpack-*.zip`. macOS official v1.3 prebuilt supports Apple Silicon; on Intel Macs compile from source. C/C++ compilation is optional if prebuilt is used. Does NOT use NVIDIA/CUDA.

Official release ZIP SHA-256:

- Ubuntu: `0666d9dc40d60fe5b9a45f3fc24f8e6ca87112974bd5de9ca57152aa13d06017`
- Windows: `f6e9c09d66af23da3da71b86f0652d2413e81c734e0aecd1cd3d0e6e6e8645c0`
- Apple Silicon: `1002fe6a437aa005eca541502c27b8d2b184f91f4ad0c6d282e3614a1e35e75a`

Khronos Validator is **mandatory** when `--meshoptimizer` is enabled. Install with `python scripts/install_gltf_validator.py --install` (or use existing `--gltf-validator-package`). No false PASS if absent.

## Commands

Default CPU creator + official safe gltfpack after GLB export:

```bash
python scripts/build_with_anatomy.py --blender blender --meshoptimizer
```

Pillow PBR → glTF-Transform dedup → gltfpack → Validator:

```bash
python scripts/build_with_anatomy.py --blender blender --xatlas-uv --pbr-cpu \
  --gltf-optimize --gltf-mode safe --meshoptimizer --meshoptimizer-mode safe
```

Explicit compressed GLB (Three.js needs `MeshoptDecoder`):

```bash
python scripts/build_with_anatomy.py --blender blender --meshoptimizer \
  --meshoptimizer-mode compressed
```

Existing game GLB without Blender:

```bash
python scripts/meshoptimizer_cpu_worker.py --input monster.glb --output monster_fast.glb \
  --mode safe --validate-khronos
```

In Three.js, if **and only if** `EXT_meshopt_compression` appears in `extensionsRequired`, configure `GLTFLoader.setMeshoptDecoder(MeshoptDecoder)` and ship the decoder in the game bundle. The safe mode needs no new compression decoder. Both modes are CPU authoring processes; WebGL is still used to render the game.

## Safety restrictions

- No `-si` (simplification), no remeshing, no `-tc/-tw` texture re-encoding, and no quantization by default. Original upstream command uses `-kn -km -ke -noq` to retain named nodes, named materials and extras.
- Blocks files with unknown extensions/custom attributes that gltfpack may discard. Rejects material/embedded image change, animations/skin/morph differences, scene restructuring or missing UVs.
- gltfpack may still resample numerical animation keys or reorder source triangles; the guard is primarily **structural**. It is not proof that every animated pose renders identically; verify by opening the generated GLB in the actual game. Strict checks may reject valid outputs to protect identity.
- `--meshoptimizer` and `--gltf-optimize --gltf-mode meshopt` cannot be combined; the input must be uncompressed because gltfpack cannot consume already meshopt-compressed glTF from glTF-Transform reliably.
- Safe mode chooses the original bytes rather than a larger GLB when gltfpack provides no download-size benefit. No gain is promised.
- The ZIP contains original Python integration and installer, not the native upstream program. Internet/DNS or a locally supplied verified official archive is required to install it.
