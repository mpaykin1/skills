# GDRETools integration — Godot recovery stage

Upstream: https://github.com/GDRETools/gdsdecomp (MIT; Copyright © 2019 bruvzg and contributors). The upstream full code and built binaries are **not redistributed** in this plugin. This skill implements executable integration against the published open-source CLI.

Verified upstream release metadata (2026-11-23): [v2.7.4](https://github.com/GDRETools/gdsdecomp/releases/tag/v2.7.4). The installer is version-pinned and authenticates official asset ZIP against GitHub release SHA-256. Installing is optional if `gdre_tools` already exists on PATH.

## Inputs and sequence

`game.pck`, `game.exe` with an embedded Godot PCK, `game.apk`, or an extracted game folder → GDRETools `--headless --recover=<INPUT> --output=<FOLDER>` → recovered `project.godot`, scripts, scenes, textures and other imported assets → matching **Godot editor** → native Web export → optional experimental single-file packaging.

Native `project.godot` input skips GDRETools entirely. This preserves the original, highest-fidelity path, and avoids unnecessary reverse engineering.

## Commands

On a machine with network access:

```bash
python skills/godot-game-to-html/scripts/install_gdretools.py
python skills/godot-game-to-html/scripts/game_to_html.py /games/owned/game.pck --out /games/build --mode web
python skills/godot-game-to-html/scripts/game_to_html.py /games/owned/game.pck --out /games/build-single --mode single
```

If only extraction is desired, or the recovered engine is Godot 2/3 and the exporter only supports Godot 4:

```bash
python skills/godot-game-to-html/scripts/game_to_html.py /games/owned/game.pck --out /games/recovery --mode recover
```

For offline installation use `install_gdretools.py --archive /path/to/GDRE_tools-v2.7.4-<OS>.zip`. SHA-256 is still checked; no network required. For an existing executable pass `--gdre /path/to/gdre_tools`.

**Important:** current upstream CLI uses `--output=`, not obsolete `--output-dir=`. Do not use the latter.

## Boundaries

- Recover only materials the user owns or is licensed to modify. Do not invent or retrieve encryption keys; `--key-env ENV_VARIABLE` is only for a key legitimately provided by the rights holder. Never log such a key.
- GDRETools cannot reconstruct all GDNative/GDExtension scripts or all original imported assets. Mono/.NET and engine-specific native modules may require substantial work and cannot be auto-exported to HTML.
- Recovered project is *not* automatically a verified playable game. Inspect the recovery log, required Godot version and the exported Web build. No arbitrary binary from the user's game is executed.
- Export of Godot 2/3 games requires a matching editor plus version-specific workflow; v1.1's `godot_to_web.py` targets Godot 4 GDScript. Stop after recover if version compatibility is unresolved.
- PCK/EXE/APK extraction may be incomplete. Preserve original extracted assets and do not replace missing 3D models or animations with placeholders.
- Godot Web export depends on available browser features. Offline single-file `file://` compatibility remains experimental; fail openly rather than shipping a static fake.
