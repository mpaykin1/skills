# Cpp2IL and ILSpy integration

- Cpp2IL official repo (MIT): https://github.com/SamboyCoding/Cpp2IL
- Development CLI source `Cpp2IL/CommandLineArgs.cs`: supports `--game-path`, `--list-output-formats`, `--output-as dll_il_recovery`, `--output-to`.
- Pin: Git commit `b5ad444b82267cb1e4b88b8b373c008105bdea52` (development branch on 2026-11-23). Newer commits may change the CLI; don't silently track moving master.
- ILSpy official repo/CLI (MIT): https://github.com/icsharpcode/ILSpy and https://github.com/icsharpcode/ILSpy/blob/master/ICSharpCode.ILSpyCmd/README.md

The adapter checks metadata and native IL2CPP binary without running any game executable. It invokes Cpp2IL on the intact licensed game directory or APK, writing approximate managed assemblies into a separate directory. If `Assembly-CSharp.dll` can be produced, ILSpy may be able to decompile it into a derivative C# project; this may be partial, distorted or contain stubs.

Do not claim an IL2CPP project was faithfully rebuilt, that script source was completely recovered, or that an autonomous HTML gameplay build was produced. Cpp2IL cannot transplant Unity C# logic into Three.js/PixiJS automatically. AssetRipper/UnityPy output scene, sprite and serialization data for independent reconstruction. Keep original Unity native WebGL export as the first choice when original Unity source is available.
