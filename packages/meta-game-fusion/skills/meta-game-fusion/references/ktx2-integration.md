# Basis Universal + KTX2 (META GAME FUSION v1.7.0)

**Purpose.** Compress embedded GLB textures for mobile GPU memory / download
cost, while preserving approved asset identity and maintaining independent
Rapier and Recast authority. Proven upstream:
- Basis Universal: https://github.com/BinomialLLC/basis_universal (Apache-2.0).
- KTX-Software: https://github.com/KhronosGroup/KTX-Software (mostly Apache-2.0; bundled third-party license exceptions; nothing from repository bundled).
- Khronos `KHR_texture_basisu`: https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_texture_basisu.
- Three.js KTX2Loader: pinned `three@0.186.1` and its Basis WASM transcoder.

## Real encoding (not metadata-only)

Requires explicitly installed `@gltf-transform/cli@4.5.1` and `ktx` command
from Khronos KTX-Software **4.4.0+**. Installation is opt-in, and cannot be
performed while the npm registry is unreachable. The `ktx` encoder invokes
Basis Universal; our Python scripts do not pretend to encode raw texture bits.

```sh
python skills/meta-game-fusion/scripts/gltf_optimize.py optimize \
  --models /scratch/library/model-library.json \
  --out /scratch/library --profile mobile-ktx2
# Alternate profiles: ktx2-etc1s (small), ktx2-uastc (higher quality)
```

`mobile-ktx2`: `dedup` -> UASTC normal+occlusion+metallicRoughness ->
ETC1S remaining textures -> meshopt geometry; preserving original scene graph,
rigs, morphs, clips and skin bones. Maps only encoded if included in the GLB.
ETC1S and UASTC both require a visual review: they are lossy compression.
If encoder is missing, the record is `unavailable` and the original model is
not mislabeled as compressed. The optimization pipeline refuses to overwrite
original models. All output SHA-256 values are pinned.

## Output and runtime integration

`fusion_builder.py` carries the approved GLB bytes into a **new** project,
`ktx2_bridge.py audit` verifies exact GLB SHA-256, `KHR_texture_basisu`
source/image references, KTX2 signatures and image ranges. The new project
contains `/ktx2-manifest.json` with *actual* counts, including zero.
`meshopt_bridge.py` independently validates `EXT_meshopt_compression`.

`src/meshopt-loader.js` now composes `GLTFLoader.setMeshoptDecoder()` with
`GLTFLoader.setKTX2Loader()`, detecting the renderer's supported GPU formats.
Before Vite starts/builds, `scripts/stage-ktx2.mjs` copies the exact pinned
`basis_transcoder.js` and `basis_transcoder.wasm` from the installed Three.js
npm package into `public/basis/`, **only when imported KTX2 models exist**.
No external CDN or silent runtime download. If either file is missing the
build fails, rather than silently replacing the approved art.

KTX2 texture compression is visual-only, does not rewrite Rapier collision
meshes, Recast navmesh, MeshBVH source rules, original game assets, or hero
animation. GPU fallback varies by device; no fixed FPS/VRAM savings claimed
without a genuine browser test. Do not call a generated source game autonomous
HTML; it requires npm and a web server.
