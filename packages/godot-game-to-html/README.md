# META GAMES · Godot + Unity → Autonomous HTML v1.24.0

**NEW official Sprite Sheet Helper (MIT)**, pinned at `Kyonru/sprite-sheet-helper@aacb362a`, brings actual headless GLB capture into **eight-direction original-art sprite atlases** with a shared fitted camera for all clips/directions. From an approved source `stack.json`, the previous MIT `sprite-in-the-round` creates a GLB from the *same* horizontal RGBA slices, then Sprite Sheet Helper exports PNG/JSON. From four orthographic views, the earlier MIT `danielwh2/sprite-stacking` first carves a true volume. Direct animated Unity/Godot GLBs retain source animations; static stacks never generate fictitious motion. Official `--format godot|unity|phaser|gif|zip|spritesheet` and normal-map outputs are available. No model/image replacement or alteration of source games.

```bash
python skills/godot-game-to-html/scripts/sprite_sheet_atlas.py SOURCE.glb --out /output/atlas --workflow three-quarter-8dir --format spritesheet
python skills/godot-game-to-html/scripts/sprite_sheet_atlas.py /approved/stack.json --out /output/native-godot --format godot
```

The upstream CLI is fetched from a pinned Git commit, built using npm and runs Puppeteer locally when invoked; Chrome and build tools are **not** shipped with this skill or resulting games. If unavailable, the export fails rather than fabricating frames. A production browser comparison via previous Playwright + Pixelmatch is still necessary.

All previous modules remain: genuine Godot/Unity WebGL and recovery GDRETools/AssetRipper/UnityPy/ILSpy/Cpp2IL; scene-level independent sprite stacks from original GLB; Manifold3D/Open3D/trimesh occupancy; Daniel White four-view carving; SoAp9035 sprite-in-the-round; Shader-Stacker Godot 4; Three.js GLSL WebGL2 volume viewer; PixiJS; Khronos glTF Validator; Basis/KTX2; xatlas/Blender/OIDN/OpenImageIO; FFmpeg/oxipng/glTF-Transform; Playwright/Pixelmatch. Native engine gameplay remains the authoritative playable version.
