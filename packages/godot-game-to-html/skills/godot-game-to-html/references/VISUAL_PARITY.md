# Mapbox Pixelmatch (ISC) — screenshot parity before optimized assets are promoted

Sibling skill: `skills/visual-parity-guard/SKILL.md`.

Godot/Unity original WebGL runtime → real screenshot at fixed viewport/camera/time. Optional derivative from xatlas/Blender/OIDN/OpenImageIO/oxipng/KTX2/glTF-Transform → comparable real screenshot. Mapbox Pixelmatch 8.0.0 + pngjs 7.0.0 compare them and block visually divergent candidate. For GLBs, Khronos glTF Validator provides complementary structural checks via existing `validate-glb.mjs`. Three.js offline visual scene is an optional *visual* output only after successful screenshot and GLB checks; native Godot/Unity WebGL remains actual gameplay.

To compare already captured PNGs:

```
python skills/visual-parity-guard/scripts/visual_parity.py --baseline original.png --candidate derivative.png --max-ratio 0.03
```

To validate the GLB and conditionally build existing Three.js viewer:

```
python skills/visual-parity-guard/scripts/visual_parity.py --baseline original.png --candidate derivative.png --original-glb original.glb --optimized-glb derivative.glb --html-out derivative-visual.html
```

No screenshot creation is implied; do not claim visually identical rendering based only on glTF schema. Dynamic effects in «ЛЕЕР» require synchronized weather/animation/exposure; otherwise result is inconclusive. Shader replacement or KTX2 source PNG replacement is forbidden without browser-side comparison and review. Threshold controls visible pixel *ratio* in supplied frames, not fraction of complete gameplay or model data retained.
