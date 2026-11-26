---
name: antopilo-spritestacker
description: Source-authentic bidirectional integration of MIT antopilo/SpriteStacker legacy Godot 3.1 Z-layer editor with Living Image Animator's real transparent PNG stack.json, Three.js 360° GLSL viewer and Godot4 Shader Stacker, retaining existing actor identity/full-cel gates and no deformation.
---
# antopilo/SpriteStacker × Living Image Animator 0.42

Read the original existing `skills/living-image-animator/SKILL.md` first and preserve all original full-body and identity/motion gates, earlier source systems and output entrypoints. The original native GUI is **Godot 3.1-era only**, NOT Godot4. Its native source is `https://github.com/antopilo/SpriteStacker`, MIT. This installed integration is a **working Python I/O bridge** and a pinned original-source checkout helper; do not claim the Windows/Godot3 editor executable or game runtime is bundled.

**Priority:** use genuine sprite stacking for all eligible architectural, vehicle, weapon, prop, machinery, scenery and authored whole-pose volume objects. No fake boxes, billboards or isolated cutout character limbs. The existing 90% eligible-asset target remains unchanged. Exact approved source artist cels must retain their identity/proportions, independent frame drawings, timing, contact and original validated hashes. A static volume does not substitute real walking/attack animation.

1. If the user supplies real Godot3 SpriteStacker `0.png`, `1.png`, etc., use `scripts/antopilo_sprite_stacker_bridge.py import-editor ORIGINAL_FOLDER OUTPUT`. This creates canonical transparent PNG slices and `stack.json` for current original Three.js and Godot/PixiJS bridges. Reject missing numerical files, non-square or non-alpha PNGs, duplicate false Z sections and giant textures.
2. If given a real canonical `stack.json`, use `scripts/antopilo_sprite_stacker_bridge.py export-editor ORIGINAL_STACK_JSON OUTPUT_FOLDER` to create numbered, byte-identical PNGs importable by the old GUI. Use numeric import order fix in genuine source when needed.
3. `scripts/antopilo_sprite_stacker_delivery.py --editor-folder ORIGINAL_FOLDER --out OUTPUT --three-js /path/to/real/three.module.js` additionally exports a correct genuine Godot 4 Shader Stacker vertical sheet, optional genuine Three.js 360 HTML, and source ZIP. The existing Godot4 ShaderStacker node renderer and Three.js GLSL renderers remain separate real existing entrypoints, not bundled into the Godot3 editor.
4. To acquire the actual original native editor **source** (not a fake binary), use `scripts/antopilo_sprite_stacker_vendor.py --out VENDOR_DIR --patch-numeric-order`, pinned Git revision and Git blob validation. Network and an actual Godot3 runtime are needed to run the editor. Existing plugin and this Python asset bridge can run without that native editor once the original PNGs are provided.

References: `skills/living-image-animator/references/antopilo-spritestacker-integration.md`; original license `skills/living-image-animator/references/LICENSE.antopilo-SpriteStacker.txt`. Preserve all original earlier source art/collision/music/GIF/APNG/WEBP/video components and prevent weakening game quality gates.
