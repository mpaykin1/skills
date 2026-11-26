# Basis Universal + Khronos KTX2 → Three.js offline bridge

Upstream: https://github.com/BinomialLLC/basis_universal (Apache-2.0); official Three.js KTX2Loader documentation: https://threejs.org/docs/pages/KTX2Loader.html; pinned `three@0.187.0` includes `examples/jsm/libs/basis/basis_transcoder.{js,wasm}`.

**Integration:** original PNG in authorized GLB → official Khronos KTX-Software `ktx2_textures.py` UASTC validated KTX2 candidate → new `embed_ktx2_glb.py` using exact original PNG byte SHA256 only → preserved PNG fallback plus `KHR_texture_basisu` in a *temporary* derivative GLB → Khronos glTF Validator (`--browser-bridge --offline-basis`) → pinned esbuild + Three.js `KTX2Loader`, `GLTFLoader` and `MeshoptDecoder` → one original-scene visual HTML embedding GLB, Basis JS/WASM and Apache license. No renderer/CDN fetch at runtime; Blob URLs and workers are created locally.

- `KHR_texture_basisu` must refer to valid embedded `image/ktx2` image; keep original PNG `texture.source` as core glTF fallback. Do not mark the extension as required while fallback exists.
- Source embedded PNG bytes and manifest `sha256` must be exactly equal. Differences from UnityGLTF/Godot texture re-encoding are a hard stop, not permission to guess from filenames. When none matches, produce no derivative.
- Candidates must have `status:candidate`, `validated_gltf_basisu:true`, KTX2 magic/valid dimension and be located under the manifest directory. Existing original GLB untouched.
- The official KTX2Loader selects device-supported GPU formats. It uses Basis Universal JS/WASM, a local Blob Web Worker, and supports relevant KTX2 transcoding. If unsupported on a browser, fail visibly rather than substituting textures.
- The `__HAS_BASIS__` esbuild build-time define removes decoder setup for ordinary GLBs. Three.js KTX2Loader contains static `import.meta.url` defaults that are rewritten only for the pinned version to avoid unintended external runtime file references. If upstream source changes, bundling fails until reviewed.
- Khronos glTF Validator still stops malformed GLB; `--offline-basis` is only for this built-in decoder, **not** a general validation bypass. Playwright/Pixelmatch still required for approval of any visual changes.
- Basis uses Apache-2.0; its license is embedded as text in the HTML. Three.js is MIT; include attribution to original source when redistributing. No binaries are vendored in the plugin archive itself.

**Limit:** a visual GLB HTML is not a game. Preserve engine native Godot/Unity WebGL for full gameplay; don't infer or invent physics, shaders, sounds, AI or C#/GDScript. KTX2 lossy texture compression is not automatically approved by a valid file/decoder.
