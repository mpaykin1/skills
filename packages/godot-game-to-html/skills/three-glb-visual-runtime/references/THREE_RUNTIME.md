# Three.js + Basis Universal renderer

- Three.js upstream MIT: https://github.com/mrdoob/three.js; pinned version `0.187.0`. esbuild `0.25.5` and official Khronos glTF Validator `2.0.0-dev.3.10` run only at build time.
- Original GLB embedded as base64, GLTFLoader + MeshoptDecoder, OrbitControls, AnimationMixer, original lights/cameras where present. Viewer-only fallback lighting is not the original Unity/Godot renderer.
- `KHR_texture_basisu`: KTX2Loader + Binomial Basis Universal JS/WASM (Apache-2.0) provided by the pinned local Three npm package, embedded into one output HTML. Local Blob workers, no network/CDN. KTX can be Zstd-supercompressed; support must be verified on actual target browser.
- If no KTX2 required, skip Basis payload, keeping output smaller. If KTX2 used, original PNG fallback stays in the GLB. Valid geometry/material/animation IDs remain mandatory.
- `KHR_animation_pointer`, Draco, glTF interactivity/variants unsupported in this bridge. Original engine WebGL preserves game logic; Three output is only a scene viewer.
- Browser `file://`, Blob workers, WASM and GPU texture format support vary; test on target browser. For each visual derivative use real Playwright screenshot and Pixelmatch compared with the original renderer.
- Any included KTX2 is lossy; never treat transcoding as proof of visual equivalence. License text and provenance must be preserved.
