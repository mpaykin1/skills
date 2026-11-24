# UnityPy 1.25.4 — Unity asset recovery (MIT)

Source: https://github.com/K0lb3/UnityPy and PyPI https://pypi.org/project/UnityPy/1.25.4/ (released 2026-10-03). Source code is MIT licensed, binary wheels are downloaded at install, not vendored.

## Why this exists alongside AssetRipper

- AssetRipper: recover the original Unity project structure, scenes, materials and asset relations where possible (GPLv3 executable kept separate).
- UnityPy: independent direct extraction of raster textures/sprites (RGBA PNG), meshes (OBJ), sound samples (WAV), text binaries, fonts and optional serialized MonoBehaviour values (MIT package).
- Original Unity source: skip both extractors and use native Unity Editor WebGL build, preserving scripts and gameplay.
- Unity compiled build: both extractors only recover resources; playable WebGL requires actual gameplay implementation. Original Unity symbols, C#/IL2CPP and components can be lost, and UnityPy does not solve that.
- Original Godot project / GDRETools recovered project: do not route through UnityPy.

## Setup (CPU-only)

```bash
python scripts/install_unitypy.py
python scripts/universal_game_to_html.py Game_Data --out output --mode recover --extractor both
python scripts/universal_game_to_html.py Game_Data --out output --mode recover --extractor unitypy
python scripts/unitypy_extract.py Game_Data --out recovered_raw --include-mono
```

`install_unitypy.py` sets up an isolated Python venv and runs `pip install --only-binary=:all: UnityPy==1.25.4`. Latest unpinned releases must not be substituted silently. Network and compatible Python wheels are required for installation; offline extract runs with a preinstalled package.

`unitypy_manifest.json`: each recovered item records type, original name, original Unity `path_id`, source file and exported paths. Keep this provenance intact to aid AssetRipper scene matching. Reused names are disambiguated with source-file hash + Unity object ID. `TextAsset` is exported as BIN to avoid breaking non-text data. `--include-mono` exports bounded JSON serializations (not executable code). If resources fail extraction, errors are recorded; do not claim a complete or faithful scene without verifying it.

The extractor refuses to write into the input tree and has maximum limits for source size, file counts, output size and asset counts. It does not decrypt protected proprietary asset formats or bypass ownership rights.

## Fidelity and autonomous HTML

Sprite and texture PNG preserve decoded alpha pixels. OBJ meshes have geometry but original Unity shaders/material graphs are not rebuilt by UnityPy alone. AssetRipper/Unity Editor remain responsible for intact Unity scene export. No engine-free HTML is synthesized from disjoint PNG/OBJ/WAV without reconstructing and validating the original game.
