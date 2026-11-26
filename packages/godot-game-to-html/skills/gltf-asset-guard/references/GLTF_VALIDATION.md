# Khronos glTF Validator integration

Official code: https://github.com/KhronosGroup/glTF-Validator
Official npm: https://www.npmjs.com/package/gltf-validator
License: Apache-2.0
Exact pinned npm version: `2.0.0-dev.3.10` (installed at build time only).

Pipeline: source Godot/Unity → UnityGLTF/GLB → xatlas/Blender/OIDN/OpenImageIO → Khronos KTX2 candidate and glTF-Transform/gltfpack → **Khronos glTF Validator** → offline Three.js GLB visualization when compatible.

The `prepare_cache()` function in `three_glb_to_html.py` installs and verifies the third dependency in the same isolated Node build cache as Three.js and esbuild. To validate a manually processed derivative, call `node <cache>/validate-glb.mjs ORIGINAL.glb --compare DERIVATIVE.glb`. The runtime HTML does not need npm, the validator or a network. To avoid passing unsupported images to an offline viewer, `--browser-bridge` rejects KHR_texture_basisu unless a separately verified KTX2 loader/transcoder is added; likewise for Draco, interactivity and unsupported animation features.

Reject structural errors and absent source animation/material identity. Warnings are not always fatal; any visual changes must still be reviewed in a browser. This does not claim improvements for «ЛЕЕР» until the real game has been built and compared.
