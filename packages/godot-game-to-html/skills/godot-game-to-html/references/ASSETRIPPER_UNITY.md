# AssetRipper 2.0.0 + Unity Editor WebGL — Integration

- Upstream: https://github.com/AssetRipper/AssetRipper, GPL-3.0; release v2.0.0 dated 2026-08-24. Source code and executable are NOT bundled. A verified installer fetches the release binary on demand. GPU not required for recovery.
- AssetRipper covers Unity assets broadly, but fidelity depends on the engine/version, export pipeline and shader formats; recovery is **not** equivalent to complete decompilation of gameplay.
- Official AssetRipper 2.0.0 uses a localhost web API. Verified from `Source/AssetRipper.GUI.Web/WebApplicationLauncher.cs` and `Pages/Commands.cs`: `--headless --port <PORT>`; `POST /LoadFolder` / `/LoadFile`, form `Path=<absolute path>`; `POST /Export/UnityProject`, form `Path=<absolute output>` and `CreateSubfolder=false`. Exported native Unity materials and resource references may still require editing.
- In the input game folder, `_Data` directory and `globalgamemanagers` can identify a compiled Unity game. Never *run* an unknown game EXE; only parse its assets via the extraction tool.
- **Original Unity project**: must include `Assets/` and `ProjectSettings/ProjectVersion.txt`. Use actual locally licensed Unity Editor with installed WebGL Build Support. The project is copied to a temporary directory. Add ephemeral C# editor BuildPipeline script for enabled scenes; do not use AssetRipper or substitute assets. Output `out/web` is the Unity original WebGL runtime. Code and game scene logic preserved to the extent supported by the native engine and WebGL platform.
- **Compiled Unity game**: use AssetRipper to recover project assets into `out/recovered_unity`. Compiled Mono C#/IL2CPP code, proprietary native plugins and gameplay state may be missing. Do NOT auto-build this as a purported playable equivalent. Need original gameplay code and/or an actual, validated port. Stop before claiming browser-playable game.
- **Single HTML**: original Unity WebGL build splits `loader.js`, `framework.js`, `.wasm`, `.data`. `pack_unity_webgl.py` inlines them into one HTML through base64 and browser Blob URLs. Supports uncompressed single-thread/default builds without StreamingAssets/worker files. This remains experimental: browsers may block `file://`, CSP, WebAssembly streaming, dynamic loader URLs, worker isolation and plugin calls. Preserve the `out/web` directory as stable fallback.
- **Graphics**: use original lighting/postprocessing until native WebGL is visually evaluated. Enhancements must be separate, reversible and not introduce new arbitrary geometry or destroy sprite fidelity. Three.js replacement is *not* automatically performed by AssetRipper. UnityPy 1.25.4 is now integrated as a separate MIT module for typed PNG/OBJ/WAV extraction; see references/UNITYPY.md. UnityGLTF remains a prospective module.
- **Licenses**: AssetRipper code is GPL-3.0, Godot/GDRETools MIT, Unity Editor is proprietary, game models/textures and recovered scripts have their own copyright/licensing. Permission to extract does not automatically permit redistribution of Unity runtime or assets.

## One-command entrypoint

```bash
# First install AssetRipper when needed (verified release, no GPU required)
python scripts/install_assetripper.py

# Original Unity source -> complete Unity WebGL build (Unity Editor must be installed)
python scripts/universal_game_to_html.py path/to/UnityProject --out output --engine unity --mode web --unity /path/to/Unity

# Original Unity source -> WebGL + experimental single HTML
python scripts/universal_game_to_html.py path/to/UnityProject --out output --engine unity --mode single --unity /path/to/Unity

# Previously compiled Unity data -> recovered Unity assets, NOT playable HTML
python scripts/universal_game_to_html.py path/to/Game_Data --out output --engine unity --mode recover --ripper /path/to/AssetRipper

# Existing Unity WebGL folder -> experimental single file
python scripts/universal_game_to_html.py path/to/WebGLBuild --out output --engine unity --mode single

# Godot original or GDRETools input routes remain available
python scripts/universal_game_to_html.py path/to/project.godot-parent --out output --mode web
```
