---
name: unity-mono-code-recovery
description: >
  Restore legally authorized Unity Mono game C# from Assembly-CSharp.dll with official open-source ILSpyCmd 11.2.0.10050. Works alongside AssetRipper recovered Unity scenes and UnityPy texture, model, audio and serialized state extraction, preserving all original assets. Never claim IL2CPP or decompiled C# instantly becomes runnable autonomous HTML.
---

# Unity Mono C# recovery — ILSpy + AssetRipper + UnityPy

**Mandatory goal:** This is a module of the user's **existing** Godot + Unity → Autonomous HTML plugin. Use the same plugin; do not create a competing converter, replace previously integrated tools or overwrite the original Unity game.

## Route

1. Classify input as a complete original Unity project, compiled Unity MONO player, or Unity IL2CPP native player. Complete original source must go directly through native Unity Editor WebGL export; skip decompilation. For an authorized compiled Mono game, find `Game_Data/Managed/Assembly-CSharp.dll`, `Assembly-CSharp-firstpass.dll`, or `Assembly-UnityScript.dll`.
2. Use **real** ILSpyCmd v11.2.0.10050 (MIT), optionally installed as a pinned .NET 10 CLI tool inside user cache. No DLL is executed; assemblies are decompiled to new C# project folders. Keep originals untouched. Exit clearly if an IL2CPP game has no recoverable managed script assembly.
3. Use AssetRipper 2.0 for Unity scenes, assets and dependencies; UnityPy 1.25.4 for original PNG/OBJ/WAV/fonts and optional serialized `MonoBehaviour` values. Keep ILSpy C# decompilation separate in `managed_csharp/csharp/Assembly-CSharp/` and preserve provenance. **Do not overwrite** AssetRipper's reconstructed project with C# guesses and don't silently remap MonoScript GUIDs.
4. Only after analyzing code-to-scene references, decide if the full Unity game can be rebuilt in the original Unity Editor; if complete original source exists, use the existing `unity_to_web.py` WebGL route. C# obtained by reverse engineering is not browser JavaScript. Do not claim playable autonomous HTML without rebuilding full gameplay, scripts and engine features and checking actual game behavior.
5. For models/visuals without logic, existing UnityGLTF → Three.js and UnityPy → PixiJS pipelines are visual previews only; don't represent them as a restored game.

## Commands

From the parent plugin root:

```bash
python skills/godot-game-to-html/scripts/universal_game_to_html.py /path/to/UnityGame_Data --out /output --mode code
python skills/godot-game-to-html/scripts/universal_game_to_html.py /path/to/UnityGame_Data --out /output --mode recover --extractor both --with-csharp
```

Standalone module and offline install mode:

```bash
python skills/godot-game-to-html/scripts/install_ilspycmd.py
python skills/godot-game-to-html/scripts/recover_unity_code.py /path/to/UnityGame_Data --out /output/managed_csharp --no-install
python skills/godot-game-to-html/scripts/recover_unity_code.py /path/to/Assembly-CSharp.dll --out /output/managed_csharp --ilspy /installed/ilspycmd
```

Dependencies: `.NET SDK >= 10.0.100` to install the tool from NuGet; .NET runtime may vary by platform. The skill's Python wrapper uses only the standard library. CPU-only source analysis; **no GPU**. No ILSpy binaries or compiled game content shipped in plugin ZIP. The installer only runs when invoked and downloads the official pinned package via NuGet.

## Limits

- ILSpy decompiles **managed Mono assemblies** to readable reconstructed C#; original comments, local identifiers, Unity GUIDs and exact source layout may be lost. Obfuscation may prevent reconstruction.
- Native IL2CPP cannot be decoded by ILSpy; different tooling and manual porting required. Do not automatically rebuild or invoke extracted DLLs. Use only games the user owns or has authorization to process.
- A reconstructed `.csproj` is not a full playable Unity project; Unity game WebGL builds require matching assets/scenes, code dependencies, settings, engine and compatible scripting.

See `references/ILSPY_MONO.md` for design and official license/CLI sources.
