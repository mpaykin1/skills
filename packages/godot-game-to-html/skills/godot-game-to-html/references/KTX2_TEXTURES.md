# Khronos KTX-Software + Basis Universal offline Three.js

**Official sources:** https://github.com/KhronosGroup/KTX-Software (KTX2 UASTC encoder and validator); https://github.com/BinomialLLC/basis_universal (Apache-2.0 Basis transcoder); https://threejs.org/docs/pages/KTX2Loader.html (Three.js runtime).

## Purpose and cooperation

1. Keep **original game source**, native Unity/Godot WebGL, source PNGs and original GLBs untouched. All changes happen in reversible derivatives, and actual browser visual parity remains mandatory.
2. `ktx2_textures.py`: official Khronos `ktx create` UASTC 4×4 encoder with Zstd; `ktx validate --gltf-basisu` confirms candidate. Color/albedo/emissive = sRGB, normal/ORM/AO = linear data. Input PNGs must be genuine 8-bit RGB/RGBA with dimensions divisible by four and max side <=8192; no palette, 16-bit or unknown color-conversion semantics. Original PNG bytes are not modified.
3. **New GLB linker:** `three-glb-visual-runtime/scripts/embed_ktx2_glb.py` takes approved `ktx2-candidates.json`. It checks the original PNG's embedded binary SHA256 against manifest SHA256. No filename guessing; if none matches, fail visibly. Add `KHR_texture_basisu` pointing at an embedded KTX2 image while keeping the original PNG as the `texture.source` fallback. The source GLB remains untouched.
4. **New offline runtime:** `three-glb-visual-runtime/scripts/three_glb_to_html.py` accepts `--ktx-manifest` and links approved candidates in a temporary GLB, validates via official Khronos glTF Validator, then bundles Three.js `KTX2Loader` and pinned local **Basis Universal JS/WASM** inside one visual HTML (no runtime CDN). `KTX2Loader.detectSupport(renderer)` chooses GPU output format; Blob worker transcoding is local.
5. Playwright screenshot capture and Pixelmatch compare rendered **original vs compressed** scenes. GPU compressed KTX2 is lossy and file size may increase due to original PNG fallback. Never silently substitute approved original art. `gltf-asset-guard` continues to reject invalid GLB and all unsupported interactive extensions.

## Commands

```bash
# sRGB color textures and linear normals/data are handled separately:
python skills/godot-game-to-html/scripts/ktx2_textures.py /assets/albedo --out /candidates/color --kind color
python skills/godot-game-to-html/scripts/ktx2_textures.py /assets/normals --out /candidates/normal --kind normal
python skills/godot-game-to-html/scripts/ktx2_textures.py /atlas/ao --out /candidates/ao --kind data

# Original GLB's embedded PNG must match candidate SHA256 byte-for-byte:
python skills/three-glb-visual-runtime/scripts/three_glb_to_html.py original.glb --out visual-ktx2.html --ktx-manifest /candidates/color/ktx2-candidates.json
# Or directly from universal entrypoint:
python skills/godot-game-to-html/scripts/universal_game_to_html.py original.glb --mode visual --out visual-ktx2.html --ktx-manifest /candidates/color/ktx2-candidates.json
```

## Restrictions

- Requires separately installed official Khronos `ktx` 5+ CLI and Pillow for encoding. The JS build requires Node.js/npm and pinned `three@0.187.0`, esbuild and glTF Validator; final HTML includes its Basis JS/WASM and license, not network files.
- Encoder candidates are kept only when smaller unless `--keep-larger` is given; this does **not** imply reduced total HTML size or pixel-identical texture shading. It targets GPU texture storage/transcoding.
- Exact original PNG hash matters: UnityGLTF/Godot can recompress embedded images, making externally encoded PNG candidates impossible to match. In that case generate a candidate from the *actual embedded PNG bytes* and do not guess or edit resource identity.
- `KHR_texture_basisu` GLB is a **visual preview**, not recovered Unity/Godot scripts, audio, physics, UI or gameplay. Always keep engine-native WebGL as the game.
- Basis Universal transcoder JS/WASM are obtained from the pinned local Three.js npm package, not bundled into plugin source ZIP. The final HTML embeds Apache-2.0 license text. Browser-specific `file://`, WASM or Blob worker limitations may prevent startup; launch in the target browser to confirm.

See `skills/three-glb-visual-runtime/references/BASIS_UNIVERSAL.md`.
