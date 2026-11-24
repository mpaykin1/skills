# Khronos UnityGLTF — original Unity scene preservation

Source: https://github.com/KhronosGroup/UnityGLTF (MIT)
Pinned UPM package: `org.khronos.unitygltf` @ `https://github.com/KhronosGroup/UnityGLTF.git#release/2.25.0`.
This is added only to a temporary Unity project copy, and is installed by Unity Package Manager. No UnityGLTF binaries or Unity Editor are included.

## What is gained

Unity native WebGL BuildPipeline is the **playable** route; UnityGLTF is its **visual extraction** companion. UnityGLTF exports scene hierarchy, original meshes, materials, textures, lights, cameras, skinning and supported animation clips in GLB. This can be inspected or converted to Three.js-compatible visual data. AssetRipper and UnityPy recover resources from compiled Unity games; UnityGLTF only operates on a *runnable original Unity project* (or sufficiently reconstructed project that actually imports and compiles, not guaranteed).

### Commands

```bash
python scripts/universal_game_to_html.py /path/UnityProject --out /path/output --engine unity --mode scenes --unity /path/to/Unity
python scripts/universal_game_to_html.py /path/UnityProject --out /path/output --engine unity --mode web --export-glb --unity /path/to/Unity
python scripts/export_unity_glb.py /path/UnityProject --out /path/output --all-scenes --unity /path/to/Unity
```

- Default: only Unity Build Settings enabled scenes. `--all-scenes`: all Unity scene assets (including non-playable test scenes).
- GLBs are written to `out/glb_scenes/`, with `gltf_manifest.json` enumerating geometry, animation, materials and extension usage.
- The original Unity source is never modified. A staged Unity clone receives UPM dependency and an Editor script that uses `GLTFSceneExporter.SaveGLB`.
- `--export-glb` runs separately after successful **native Unity WebGL** build. On GLB failures, the original `out/web/` playable export is preserved.

### Limitations

GLB is **not** a standalone game; compiled C#/IL2CPP, physics, scene flow, game rules and many shaders are not part of glTF. `KHR_animation_pointer`, `KHR_interactivity`, and `KHR_audio` may not be fully supported by Three.js; manifest records them for browser compatibility checks. UnityGLTF's HDRP support is limited. When custom material/shaders do not round-trip, retain the official Unity WebGL output as visual baseline. No automatic "enhancement" that changes original colors, light behavior or art style.

### Licensing and runtime

UnityGLTF MIT; Unity Editor remains proprietary and is not shipped. Pinned package requires Unity 2022.3 or newer (per UnityGLTF package.json). Unity package download requires network on the machine running Unity Editor. CPU-only asset processing is possible; interactive browser rendering still needs WebGL-capable GPU. Export requires legitimate project access and relevant resource rights.
