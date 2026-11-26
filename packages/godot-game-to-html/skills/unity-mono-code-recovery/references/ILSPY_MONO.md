# ILSpy 11.2.0.10050 — managed Unity C# bridge (MIT)

- Official source and CLI: https://github.com/icsharpcode/ILSpy and https://github.com/icsharpcode/ILSpy/blob/master/ICSharpCode.ILSpyCmd/README.md
- Official NuGet tool: https://www.nuget.org/packages/ilspycmd/11.2.0.10050 (2026-10-27)
- MIT license: https://github.com/icsharpcode/ILSpy/blob/master/LICENSE

The `install_ilspycmd.py` script installs only an isolated pinned tool under `~/.cache/godot-unity-to-html/ilspycmd/11.2.0.10050`, not globally. Requires separately installed .NET SDK >=10.0.100. No ILSpy binaries included.

`recover_unity_code.py` discovers `Assembly-CSharp.dll`, `Assembly-CSharp-firstpass.dll`, `Assembly-UnityScript.dll` from Unity `Managed` folders or accepts explicit DLL inputs. It uses the official CLI:

```text
ilspycmd --disable-updatecheck --project --nested-directories --outputdir DEST --referencepath MONO_MANAGED_DIR Assembly-CSharp.dll
```

It writes reconstructed `.cs` and `.csproj` into fresh output paths; `ilspy_manifest.json` preserves input SHA-256 and file counts for matching classes with original Unity scene data. It does not produce a scene map by itself.

### Cross-tool contract

- AssetRipper restores serialized scenes / meshes / materials / MonoScript references when possible.
- UnityPy restores original visual/audio assets and optional serialized MonoBehaviour values.
- ILSpy reconstructs managed C# classes to read their game logic, where Mono assembly data exists.
- UnityGLTF / Three.js reconstructs visual GLB representation only. PixiJS renders original sprites only.
- Unity Editor builds an actual playable WebGL game only when the scripts, project and dependencies work together. Rebuilding a damaged or obfuscated project is a separate work stage; don't invent gameplay or certify it from assets alone.

IL2CPP games (`GameAssembly.dll`, `libil2cpp.so` plus `global-metadata.dat`) are explicitly outside this module. They require IL2CPP-native analysis and a separate faithful port; no guarantee of original C# recovery.
