# Khronos glTF-Validator — META GAME FUSION v1.8.0

- Upstream: https://github.com/KhronosGroup/glTF-Validator
- License: Apache-2.0; preserve `vendor/gltf-validator/LICENSE`.
- Pinned npm runtime: **`gltf-validator@2.0.0-dev.3.10`** (compiled Dart validator).
- API: `validateBytes(new Uint8Array(bytes), {uri, format:'glb', maxIssues:100, writeTimestamp:false, externalResourceFunction})`. Official docs: `node/README.md` and `node/module.mjs` in upstream.

## Why it strengthens the existing modules

`Assimp` / `Manifold` produce converted or procedural glTF geometry; `glTF-Transform` compresses it, `meshoptimizer` encodes geometry, and `Basis/KTX2` encodes textures. Existing Python bridges check asset rights, hashes, GLB2 headers and known extension ranges. **Those are not full specification validation.** Khronos Validator adds binary accessor, scene, skin, animation, material and structural correctness checks on the **exact final GLB bytes** before Three.js imports them.

In `fusion_builder.py`, approved assets are SHA-pinned, rights-gated and copied into a new generated project. `scripts/validate-assets.mjs` runs automatically during `npm run dev`/`npm run build`; it validates every GLB with the actual npm engine, refuses unsupported execution contexts, stale/missing hashes, missing npm package and every spec error. External references are forbidden (all approved GLBs must be self-contained). It writes a local `public/gltf-validation-manifest.json` only after completion; any failure clears the old stamp. `src/meshopt-loader.js` checks the exact matching `src` and `asset_sha256` before loading; then verifies the downloaded GLB hash independently. Approved static meshes alone enter MeshBVH; Rapier owns collision; Recast owns navigation. Validation is read-only and no source game is changed.

`gltf_validator_bridge.py validate --project <generated-game>` runs the same gate explicitly. `verify` checks that the local approval metadata still matches current file hashes. No report files are emitted to the user. The npm package is **not bundled** and installation is manual; when unavailable, the gate fails closed on any imported models. Empty original concept builds contain no approved GLBs and record `no-GLB-assets-to-validate` without pretending validator execution.

The validator can warn on some extensions without interpreting all their encoded payloads; `meshopt_bridge.py` and `ktx2_bridge.py` remain independent, and a PASS on structural integrity does not prove correct rendering, commercial license, hero identity or smooth gameplay. These remain separate gates. Build must not be advertised as browser-tested without actual browser verification.

Commands:

```sh
python skills/meta-game-fusion/scripts/fusion_builder.py build --library /absolute/library --concept 'Пепельный виадук' --out /absolute/new-game
# Then, inside the newly generated game with network available:
npm install --ignore-scripts
npm run validate:assets
npm run build
```
