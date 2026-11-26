# Khronos glTF-Validator — CPU-only integration (v1.3.0)

- **Official project:** https://github.com/KhronosGroup/glTF-Validator
- **Package:** https://www.npmjs.com/package/gltf-validator
- **Version:** `gltf-validator@2.0.0-dev.3.10` (Apache-2.0), CPU / Node.js.
- **Reviewed source HEAD:** `602c54043ba66856b2e68c40fdf2bced975cdb8a` (2026-10-06).
- Full upstream, compiled Dart runtime and npm packages are **not bundled** in this skill. The install helper obtains the real, pinned official npm package when network is available. No automatic fetching from the game build.

## Synergy with existing sources

1. PyMeshLab repairs **eligible unskinned static** meshes before binding; Instant Meshes lowers polygon density on explicitly approved shapes.
2. Blender + MyoGeneratorRemix produce the **single original monster**, muscle weights, `ANATOMY_FLEX` / `ANATOMY_STRETCH` and NLA clips.
3. Rigger / Open Mocap add **new actions to the same armature**; they do not replace the model.
4. glTF-Transform optionally de-duplicates the final GLB on CPU; Meshopt compression is opt-in and requires Three.js decoder.
5. **Khronos glTF-Validator** validates GLB 2.0 headers, buffer references, accessor data, skins and animations via its **actual official `validateBytes` API**. If validation fails, downstream gameplay file is **not approved**. No geometry, rig or clip is mutated by validation.

The skill has its own conservative GLB before/after structure checks in `scripts/gltf_transform_worker.py`. Khronos adds standards-based validation — it does **not** replace the structure guard or guarantee visual similarity, shape-key quality, FPS, root motion, or Three.js decoder support.

## CPU setup

```sh
python scripts/install_gltf_validator.py --install
```

Offline, a previously installed official npm package may be referenced using `--gltf-validator-package /path/to/node_modules/gltf-validator` or environment `GLTF_VALIDATOR_PACKAGE`. If neither is available, the validator exits with an explicit error; **never report PASS without running Khronos code**.

## Usage

Validate an existing GLB with NO Blender:

```sh
python scripts/gltf_validator_worker.py --input /path/monster.glb
```

Use together with CPU building and optional glTF-Transform dedup:

```sh
python scripts/build_cpu_only.py --blender blender --gltf-optimize --gltf-validate
```

Without optimizer:

```sh
python scripts/build_with_anatomy.py --blender blender --gltf-validate
```

`--gltf-validate` validates original export **before** optional glTF-Transform and validates final GLB **after** optimization, failing on Khronos errors. `--gltf-validate-strict-warnings` additionally blocks warnings. It emits only a short console summary, **no separate report artifact by default**.

## Safety and limitations

- `extensionsRequired` not supported by this pinned validator, or any GLB with **external buffers/textures**, are rejected as *not fully validated*; especially relevant for `EXT_meshopt_compression`. Verify Three.js loader decoder independently if using Meshopt.
- Old plugin documentation mentions unsupported GPU projects (TRELLIS.2 and SkinTokens). Those remain disabled in CPU-only mode.
- Requires Node.js and actual official npm runtime, not a mock. No network access at validation time once installed.
- The model and animations may be technically valid yet still look incorrect, have a broken pose, or clip through surfaces. Inspect approved artwork in the game.
- This runtime has no reachable npm DNS and no Blender; the current build contains **working wrapper source and install manifest**, not a proven completed official runtime validation.
