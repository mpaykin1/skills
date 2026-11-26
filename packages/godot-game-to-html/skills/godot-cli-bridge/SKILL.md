---
name: godot-cli-bridge
description: Real Godot 4 headless scene management and native Web export via pinned CLI-Anything; preserve original graphics, scripts, physics and source-authentic sprite stacks.
---
# Godot CLI bridge
Source https://github.com/HKUDS/CLI-Anything/tree/34f519533bc175d2fe287ab8316b0dd99bb9cc43/godot/agent-harness
Installer https://github.com/mpaykin1/skills/blob/main/packages/skill-synergy-manager/scripts/install_godot_cli.sh ; free disposable Linux x86_64 worker; Godot 4.5.1 and matching export templates verified against fixed upstream release digests. Python dependency versions fixed, hashes not locked.
Use existing Godot source engine and matching version for an actual game, never silently migrate an older project. The 4.5.1 worker is a candidate only until actual export succeeds. Never execute untrusted GDScript. Copy an authorized project into lab, hash original assets and preserve main_scene, physics, rig, original full animation frames, music, lighting and shaders. Use CLI to inspect project scenes/scripts/resources, edit an independent SpriteStackAssets scene, reimport, validate trusted scripts, and export a configured Web preset. Native Godot gameplay is authoritative. Three.js visual derivatives are not equivalent games. GLB from Blender, transparent RGBA from existing Sprite Stacking, and MIDI/WAV from MUSIC are imported as source-authentic assets; existing Shader-Stacker, glTF validator and Playwright visual parity remain required. Never substitute primitives or synthetic characters in actual games. Use Compatibility in a copy for Web export only; verify effects visually and preserve original source. Single-file offline conversion requires the existing packer and actual browser verification; normal Web export is multi-file.
Commands (absolute paths, disposable trusted project):
```sh
cli-anything-godot --json engine status
cli-anything-godot --json -p /absolute/project project scenes
cli-anything-godot --json -p /absolute/project scene read scenes/Level1.tscn
cli-anything-godot --json -p /absolute/project export build --preset Web --output /absolute/output/index.html
```
Parse JSON status and returncode, not just process exit. Native output and actual browser rendering are separate readiness gates. Keep existing animated-world/black-screen guards. No automatic commit to meta6 or publication. The workflow creates only a disposable technical fixture, not a playable game or approved asset.
