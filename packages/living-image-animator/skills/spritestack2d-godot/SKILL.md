---
name: spritestack2d-godot
summary: Genuine MIT SpriteStack2D native Godot 4 source addon integrated into Living Image Animator, using exactly the same approved painted Z-slice source volumes and original full-body actor cel timeline and collisions.
description: Use this skill for native Godot 4 sprite stacking from original source 2x2 orthographic PNG views or faithful projections of approved XY/Z PNG stacks; preserves Godot gameplay, PixiJS/Matter/YUKA browser game, Three.js GLSL and all prior source art checks. Never substitute fake or procedural characters.
---

# SpriteStack2D Godot × Living Image Animator (v0.39.0)

Use the full permanent animation/identity/gait source validation from `../living-image-animator/SKILL.md`. Before building, read `../living-image-animator/references/spritestack2d-godot-integration.md` and original `../living-image-animator/references/LICENSE.SpriteStack2D.txt`.

**Native Godot renderer:** upstream https://github.com/VitSoonYoung/SpriteStack2D pinned at Git revision `65f6d8dee65575ef3ee0f164698a2a1ecf93872b` and official MIT license. Its runtime requires real 2×2 TOP/FRONT/SIDE/BACK source artwork; it is neither a generic Z-slice strip renderer nor a substitute for the separate genuine Three.js full-volume GLSL renderer.

**Workflow:** validate the real original approved scene/GIF/asset ZIP, original full-body cels and per-pose stack provenance → call existing original `blender_delivery.py` (includes Godot core project) → `scripts/spritestack2d_delivery.py` invokes `spritestack2d_vendor.py` and `spritestack2d_bridge.py` → use real artist-supplied four views when present or deterministically project the author-painted source Z-sections without repainting or stretching → build an **additional, runnable native Godot project** using official SpriteStack2D addon. Original actor.gd continues to choose the full-body action and own route/physics, the corresponding approved volume views follow the exact original frame; none of these components re-author or deform character artwork. Static structures and vegetation may use additional volume source views; all original object IDs and >=90% standard eligible coverage remain valid.

Run:
```bash
python scripts/spritestack2d_delivery.py source.png --scene scene.json --out output --fps 24 --seconds 48 --fetch-addon
```

Require real GitHub/network for `--fetch-addon` or a checked authentic source checkout supplied to `--addon-root`. Native project import verification only when actual compatible Godot binary is provided. Preserve all existing PixiJS, YUKA, Matter.js, nipplejs, Three.js, Blender, Godot, FFmpeg, Howler and original GIF/APNG/WebP artifacts. Unsupported source inputs fail visibly; no visually primitive fallbacks or missing actor pose substitution.
