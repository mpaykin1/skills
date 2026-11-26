---
name: unity-il2cpp-code-recovery
description: >
  Cpp2IL IL2CPP reconstruction for licensed Unity compiled builds, followed by ILSpy C# reading. Complements AssetRipper, UnityPy, UnityGLTF, Three.js and PixiJS in the same Godot+Unity autonomous HTML skill. Do not mistake partial recovered managed DLLs for original Unity C# gameplay or a playable browser game.
---

# Unity IL2CPP recovery — Cpp2IL + ILSpy

This is a module of the **existing** `godot-game-to-html` plugin. Never create a duplicate plugin or modify original game binaries. Always prefer a complete original Unity project and official Unity WebGL for actual gameplay.

## Chain

- Unity IL2CPP compiled build with `global-metadata.dat` and `GameAssembly.dll`, `GameAssembly.so`, `GameAssembly.dylib` or `libil2cpp.so` → real Cpp2IL development CLI → approximate managed `.dll` assemblies.
- Approximate DLLs → ILSpy 11.2 where readable → reconstructed C# classes/methods, possibly incomplete, incorrect or stubs. **Never** claim recovered C# is identical to original and never automatically run it.
- AssetRipper 2.0 independently supplies scenes, Unity assets and serialization; UnityPy supplies textures, sprites, meshes and audio. Preserve source paths and IDs to match data, methods and scene components manually.
- UnityGLTF + Three.js and PixiJS supply visual HTML scenes. None recover Unity physics, AI, quest flags, GUI transitions or full logic automatically. Only original Unity source (and matching Unity Editor/WebGL module) can be natively exported as-is. A manually reconstructed project is a separate conversion, requiring actual gameplay verification.
- Godot Engine + GDRETools route unchanged. For Unity **Mono** choose ILSpy directly, without Cpp2IL.

## One-command route

```bash
python skills/godot-game-to-html/scripts/universal_game_to_html.py /authorized/UnityGame --out /output --mode code --code-backend auto
python skills/godot-game-to-html/scripts/universal_game_to_html.py /authorized/UnityGame --out /output --mode recover --extractor both --with-csharp
```

`--code-backend mono|il2cpp|auto` explicitly selects engine scripting type when needed. For IL2CPP `--cpp2il /path/to/Cpp2IL` chooses an existing official executable. Default can build pinned source only when needed. `--no-install-cpp2il` refuses network and requires it to be installed. `--no-decompile-il2cpp` outputs only recovered DLLs; ILSpy is optional. On compiled Unity game, `--mode web|single` remains blocked without functional game source, to prevent fake playable HTML.

Standalone:

```bash
python skills/godot-game-to-html/scripts/install_cpp2il.py
python skills/godot-game-to-html/scripts/recover_il2cpp.py /authorized/UnityGame --out /output/il2cpp --install-cpp2il --install-ilspy
```

Cpp2IL source pinned to commit `b5ad444b82267cb1e4b88b8b373c008105bdea52` of `SamboyCoding/Cpp2IL` development (MIT). An installed Cpp2IL with `--list-output-formats` containing `dll_il_recovery` is accepted. Pinned source build requires Git, network for source/NuGet and .NET SDK >= 10. No Cpp2IL executable or third-party game files vendored. The older official release `2022.0.7` lacks the required newer CLI format and is **not** silently substituted.

## Outputs and fidelity

- `cpp2il_dlls/`: recovered **approximate** DLL assemblies.
- `ilspy_csharp/`: C# read by ILSpy if possible.
- `cpp2il_manifest.json`: source markers, DLL hashes, incomplete C# status and explicit `playable_html=false`.
- `cpp2il_output.txt`: original tool output (diagnostics only).

Cpp2IL is a native-code reverse-engineering tool, not a full IL2CPP to C# source restorer. Encrypted, obfuscated, novel or unsupported Unity versions can fail. Never try to bypass protection. Use only games/assets the user has permission to work on. Source input is read-only; output must be in a separate directory. For upstream CLI details and license see `references/CPP2IL.md`.
