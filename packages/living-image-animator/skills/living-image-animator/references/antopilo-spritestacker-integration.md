# antopilo/SpriteStacker (MIT, Godot 3.1 editor) + Living Image Animator v0.42.0

**Real upstream:** https://github.com/antopilo/SpriteStacker , MIT © Antoine Pilote, commit `20b8b3ffae50e709292a428347997a89d38379b6`.

## Honest compatibility

The authentic Antopilo SpriteStacker is a **standalone Godot 3.1 Beta-era drawing editor** with a Z-layer panel and preview. It is **not** a Godot 4 addon, game runtime, Three.js renderer, or an automated 3D reconstructor. The original `source/Content/Export.gd` exports one `0.png`, `1.png`, ... for each layer, in drawing-layer order, to a user-chosen folder. The native `source/Content/Drawingboard.gd` importer does **not** sort directory entries, so a Godot 3 source patch is available for deterministic numeric import. Do not claim this GUI was launched or a Windows executable is bundled if it has not been.

## Integration: same art, multiple engines

1. Artist edits source 2D/2.5D **Z-slices** in the genuine old SpriteStacker GUI (Godot 3.1 runtime must be available), then exports `0.png` to `N.png`.
2. `antopilo_sprite_stacker_bridge.py import-editor ORIGINAL_FOLDER OUTPUT` validates numerical order, 8..160 actual alpha PNGs on the same 16..512px square XY canvas, at least 4 distinct nonempty slices and at least some transparent pixels, bounds source memory, and copies each PNG **byte-for-byte** to `layers/0000.png` etc. Produces canonical `stack.json` with original `spacing`, `pivot`, `size`, and `layers`. An actor's `source_pose_sha256` can only come from an externally verified *exact* original approved pose PNG; never infer this value or bypass original full-body gates.
3. This **same** canonical `stack.json` feeds installed genuine `sprite_stack_asset_preview.py` (`Three.js` WebGL2/GLSL actual 3D volume), installed `shader_stacker_bridge.py` (Godot 4 source RGBA bottom-to-top sheet), and separately the `sprite_stacking_game` PixiJS/Matter/YUKA asset path. Those renderers have different camera and physical capabilities; do **not** pretend one combined executable includes all of them.
4. `antopilo_sprite_stacker_bridge.py export-editor ORIGINAL_STACK_JSON EDITOR_FOLDER` preserves original source PNG bytes in numbered `0.png,1.png,...`; the artist can resume editing in legacy Godot 3 GUI, then roundtrip again. Prefer the optional patched native import numeric order to avoid the upstream unsorted `Directory.get_next` behavior.
5. `antopilo_sprite_stacker_delivery.py --editor-folder EDITOR_FOLDER --out OUTPUT [--three-js /path/to/official/three.module.js]` produces canonical source, regenerated native-editor folder, correct Godot 4 **one-column sheet with bottom Z slice at bottom row**, source-preserving 360° HTML only when genuine Three.js ESM supplied, and an asset ZIP with MIT notice. No source character from original scene is invented, moved or substituted. The stacked volumetric asset is only an asset, not proof of approved actor animation/game physics. No external services or downloaded images are needed for this conversion.
6. `antopilo_sprite_stacker_vendor.py --out /path/to/SpriteStacker [--patch-numeric-order]` fetches genuine upstream repository via git pinned revision and verifies source Git blobs for `Drawingboard.gd`, `Export.gd`, `project.godot`. Optional deterministic sorting patch is made only after verification. It does **not** build or run the legacy native editor; original Windows executable is not bundled. Requires network access for first clone.

## Required quality/security contract

- Every source layer remains RGBA from the original artwork; no artificial textures, flat billboards masquerading as 3D, procedural replacement poses, automatic new views or destructive quantization.
- Original actor full-body 24+fps / 40–60s gate, ≥2 meaningful actions, ≥12 frames/8 unique whole-body drawings per action, ≥22% body/joint displacement, original motion IDs/alpha and foot contacts **remain mandatory for game characters**. Editing Z-slice props alone does not certify characters or permit substituting missing pose stacks.
- Canonical original `stack.json` must reference at least four distinct actual sections, preserve bottom-to-top `layers` order, original XY/Z spacing and pivot. Godot 4 uses the exact same colors with vertical sheet row reversal, verified by pixel-level round-trip.
- Godot 3 standalone editor is NOT Godot 4 Shader Stacker. The new extra asset ZIP does not change earlier original GIF, PNG, Three.js, Godot4, PixiJS/YUKA, Rhubarb, Howler or FFmpeg outputs.

### Commands

```bash
python scripts/antopilo_sprite_stacker_vendor.py --out vendor/antopilo-SpriteStacker --patch-numeric-order
python scripts/antopilo_sprite_stacker_bridge.py import-editor old_editor_sprite/ new_stack/ --spacing 0.1 0.1 0.1 --pivot 0 0 0
python scripts/antopilo_sprite_stacker_bridge.py export-editor new_stack/stack.json old_editor_for_reedit/
python scripts/antopilo_sprite_stacker_delivery.py --editor-folder old_editor_sprite/ --out output/ --three-js genuine/three.module.js
```
