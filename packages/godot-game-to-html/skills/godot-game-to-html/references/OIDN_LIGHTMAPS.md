# Intel Open Image Denoise 2 — CPU lightmap cleanup

Upstream: https://github.com/RenderKit/oidn · Apache-2.0 · docs: https://www.openimagedenoise.org/documentation.html

## Role

**After** xatlas has generated non-destructive UV2 and Blender Cycles has baked static ambient occlusion to separate PNG files, use the OIDN 2 CPU RT filter to denoise the baked AO only. It makes low-sample baked AO look less grainy; it does **not** sharpen original textures or reproduce desktop volumetric fog, postprocessing or original shaders. The source GLB, original texture UV0, materials, scenes, character animation, original AO PNGs and gameplay remain untouched.

OIDN's `RTLightmap` filter expects HDR lightmaps; the Blender xatlas stage currently produces *LDR PNG AO*. Therefore the adapter deliberately uses the `RT` filter (`hdr=false`, optional `srgb=true`) rather than incorrectly invoking `RTLightmap`. A future EXR/HDR stage should use `RTLightmap` with linear float input separately.

## Implementation

- `scripts/oidn_lightmaps.py`: ctypes bindings to the real OIDN C99 API (`oidnNewDevice(CPU)`, `oidnNewFilter(RT)`, `oidnSetSharedFilterImage`, `oidnExecuteFilter`) with explicit device error handling, float32 arrays and 8-bit PNG output. Requires installed official OIDN 2 shared library, NumPy and Pillow. No native binaries, model weights or fonts are shipped in the plugin.
- `scripts/xatlas_lightmaps.py --bake-ao --denoise-ao`: checks the OIDN runtime before launching Blender; produces `ao/*_AO.png` and **independent** `ao-denoised/*_AO_oidn.png`; adds additive `oidn` metadata to `atlas-manifest.json`. `--oidn-strength 0.7` retains 30% of original baked detail to reduce the risk of over-smoothing.
- No automatic material replacement. Godot Web and UnityGLTF/Unity WebGL baselines remain authoritative. `oxipng` may *losslessly* compress the derivative PNGs; `glTF-Transform`/meshoptimizer may separately optimize a validated derivative GLB. Other META GAMES skills may use the denoised AO sidecars for **static environment assets** if before/after in-game inspection passes.

## Examples

```bash
python skills/godot-game-to-html/scripts/xatlas_lightmaps.py ORIGINAL_STATIC.glb --out atlas --bake-ao --denoise-ao --size 512 --samples 24 --oidn-lib /installed/libOpenImageDenoise.so.2
python skills/godot-game-to-html/scripts/oidn_lightmaps.py --input-dir atlas/ao --out-dir atlas/ao-denoised --strength 0.7 --oidn-lib /installed/libOpenImageDenoise.so.2
```

`--oidn-lib` is optional when the operating system can locate `libOpenImageDenoise.so.2` / `OpenImageDenoise.dll` / `libOpenImageDenoise.2.dylib`. No installer runs automatically. OIDN is CPU-only for this path. If missing, fail with an explicit error; do **not** silently replace OIDN with a Gaussian blur or alter the base game.

## Limits

- Only raytraced *baked* AO/lightmaps created by the approved xatlas/Blender flow. Not intended for photos, original diffuse textures, normal/roughness maps, movie frames or pixel-art characters.
- OIDN is **lossy** denoising: too much denoising can remove subtle contact shadows and cause seams at UV islands. The resulting AO PNG is a **candidate**, not an automatic upgrade. Keep original AO, compare on the target WebGL renderer before applying it to a game.
- Web export may not support Godot desktop Forward+ fog and some shaders. Denoising an AO PNG cannot solve renderer compatibility by itself.
- Open-source library integration includes working adapter code and a documented external dependency; no claim that OIDN was run on «ЛЕЕР» without the official native library and game assets.
