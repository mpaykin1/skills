# meshoptimizer v1.3.0 — compressed visual geometry and verified loading

Upstream: https://github.com/zeux/meshoptimizer (MIT, license file vendor/meshoptimizer/LICENSE.md); verified 2026-11-23. Release v1.3, 2026-09-25. npm dependency: `meshoptimizer@1.3.0`. Dependency source/WASM is **not** bundled in the plugin because network installation is unavailable in this session. This is an authored runtime integration with installable pinned dependency and source references, **not** a cloned upstream repository.

## Actual integration across modules

- Tree-sitter + Assimp inventories approved original model files and their SHA-256.
- glTF-Transform 4.5.1 `gltf_optimize.py optimize --profile meshopt` performs actual `dedup` and `meshopt` compression **if** its CLI is installed, generating `EXT_meshopt_compression` GLB2.
- ScanCode + approved Rete blueprint are mandatory before copying any non-original model into a game. Source and optimized bytes are hashed again by `fusion_builder.py` and `rapier_bridge.py`.
- `meshopt_bridge.py` audits copied GLB byte digests, compressed buffer-view headers, required extension support and produces `/meshopt-manifest.json`; generation fails closed when invalid.
- New world's `visual_geometry_pipeline` declares meshoptimizer dependency, original/optimized provenance, and visual-only scope. `fusion-build.json` records compressed asset counts accurately, including zero when no approved assets exist.
- `src/meshopt-loader.js` uses `GLTFLoader.setMeshoptDecoder(MeshoptDecoder)` with `meshoptimizer/decoder`, verifies SHA-256 *in the browser before parsing*, and returns decompressed BufferGeometry. `src/main.js` indexes static models in MeshBVH **after** decode. Inaccessible/mismatched approved models now cause a visible startup error; they are not substituted or skipped silently.
- Rapier remains authority for collisions; Recast/Detour remains authority for NPC routes; generated Manifold/three-bvh-csg architecture is not compressed in the live runtime. Neither hero identity nor animations nor original game code are altered.
- Qdrant lexical engine catalog indexes the authored verified meshopt loader, not third-party source/media.

## Requirements

Install dependencies in generated project with `npm install --ignore-scripts` when network access is available. To *compress*, install pinned `@gltf-transform/cli@4.5.1` in `optimizer-deps` first. `meshoptimizer` is an additional pinned dependency for **decoding**. glTF optimization is opt-in; an asset is not labeled compressed merely because the package is installed. Run the real game in Chromium and Safari/mobile before claiming visual equivalence or FPS gain.

## Important constraints

Vertex quantization can be lossy; never claim that meshopt always preserves all vertex coordinates exactly. The optimizer's structural preservation checks do not establish pixel or gameplay equivalence. A compressed GLB is a visual asset only. No automatic permission to reuse code or graphics arises from compression.

If npm/WASM are unavailable, generated source remains installable later, but the browser scene is **unverified**. Never describe the file as an autonomous single-HTML build or a hosted game without proof.
