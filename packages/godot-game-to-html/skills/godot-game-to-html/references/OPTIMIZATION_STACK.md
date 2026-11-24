# Open-source fidelity and compression stack · v1.9

All processing acts on copies/derivatives. Original game sources and materials are immutable.

| Component | Upstream | Role |
| --- | --- | --- |
| Godot Engine | https://github.com/godotengine/godot | Original Godot gameplay and Web renderer |
| GDRETools | https://github.com/GDRETools/gdsdecomp | Authorized packed Godot recovery |
| Unity Editor | https://unity.com | Native Unity playable WebGL export; proprietary, separately installed |
| AssetRipper | https://github.com/AssetRipper/AssetRipper | Authorized compiled Unity resource recovery |
| UnityPy | https://github.com/K0lb3/UnityPy | Unity source textures/models/audio with provenance |
| UnityGLTF | https://github.com/KhronosGroup/UnityGLTF | Original Unity scene GLB, NOT gameplay |
| Three.js | https://github.com/mrdoob/three.js | Offline original GLB **visual** HTML; use original WebGL for gameplay |
| xatlas / xatlas-python | https://github.com/jpcy/xatlas | Secondary UV2 lightmap mapping, original UV0 unaffected |
| Blender | https://github.com/blender/blender | CPU AO bake to separate sidecar textures |
| Intel OIDN | https://github.com/RenderKit/oidn | Optional CPU cleanup of new baked AO lightmaps |
| OpenImageIO | https://github.com/AcademySoftwareFoundation/OpenImageIO | HDR/EXR inspection and explicit color space conversion |
| oxipng | https://github.com/oxipng/oxipng | Lossless PNG compression |
| Khronos KTX-Software | https://github.com/KhronosGroup/KTX-Software | **NEW** UASTC KTX2 candidate compression + `ktx validate --gltf-basisu` |
| glTF-Transform | https://github.com/donmccurdy/glTF-Transform | Opt-in model dedup/prune on derivatives |
| meshoptimizer / gltfpack | https://github.com/zeux/meshoptimizer | Optional derivative geometry compression |
| FFmpeg | https://github.com/FFmpeg/FFmpeg | Optional compressed audio |

**Required boundaries:** KTX2 is lossy and requires KTX2Loader/Basis transcoder in the target browser. The current offline Three.js GLB runtime does not embed that decoder yet. Godot/Unity source engines may not accept the generated external KTX2 through their normal importer. Never apply KTX2 candidates automatically. Original native game WebGL always exists as rollback. See `references/KTX2_TEXTURES.md`.
