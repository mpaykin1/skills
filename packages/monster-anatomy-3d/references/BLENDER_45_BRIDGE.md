# Blender 4.5.16 LTS — fourth open-source integration

Official source: https://projects.blender.org/blender/blender (tag `v4.5.16`, commit `3f6797307da591fd6feb47013bd117ec557931a7`).
Official binaries and SHA256 manifest: https://download.blender.org/release/Blender4.5/ .
Blender GPLv3+ code. Art made in Blender is not automatically GPL-licensed.

## Actual division of labor

- **MPFB2**: a separate, licensed CC0 anatomical donor mesh and its game-engine rig; does NOT replace the distorted horror silhouette.
- **Z-Anatomy**: labeled anatomical reference objects and manually positioned origin/insertion markers. Its library itself is not redistributed in game assets and may contain noncommercial third-party pieces.
- **MyoGeneratorRemix**: individual editable *real mesh* muscle bellies authored with origin/insertion objects, curves and profiles; does not automatically reconstruct anatomy.
- **Blender 4.5**: skeletal deformation, secondary Flex/Stretch shape keys, NLA morph clips, hidden sculpt-workbench copies and filtered game GLB export.

## Install official Blender

Run on a network-connected Windows x64 or Linux x64 workstation:

```
python scripts/download_blender.py
```

The installer checks upstream `blender-4.5.16.sha256` and verifies the downloaded portable Blender binary before extraction. You may also use an existing Blender 4.5+ installed by your OS.
To download Blender source instead of the binary:

```
python scripts/download_blender.py --source-only
```

This clones the official Git tag and validates its exact commit SHA; source is not built or installed automatically. Blender is **not bundled in the plugin ZIP**. Current ChatGPT runtime has no Blender executable and its DNS blocks official downloads; no runtime claim is made.

## Full integration

```
python scripts/build_with_anatomy.py --blender blender --output-dir build/monster --workbench-copies
```

Or on a host with network access but no Blender yet:

```
python scripts/build_with_anatomy.py --install-blender --output-dir build/monster --workbench-copies
```

Default now runs Blender's 4th stage AFTER source download, creation of original rigged monster blockout, Z-Anatomy anchor preparation and MPFB donor/correspondence. `--skip-blender-detail` preserves earlier v0.3 results when needed.

Outputs: `monster_blender_sculpt_ready.blend` (game creature + donor references + high-res editable sculpt copies), `monster_muscle_deform.glb` (ONLY MONSTER_RIG with original creature meshes; no MPFB or Z atlas meshes).

## Real authored muscle transfer

Create a muscle with the upstream MyoGeneratorRemix Blender addon. Rename its resulting mesh exactly `<tag>_muscle` to match an origin marker `ZA_ORIGIN_<tag>` and insertion marker `ZA_INSERTION_<tag>`, OR set custom property `monster_muscle_tag` to `<tag>`. The 30 marker tags come from `scripts/z_anatomy_bridge.py`.

`scripts/myo_rig_bridge.py` matches the pair, preserves world space, weights the actual muscle mesh between corresponding MONSTER_RIG bones, attaches a Blender Armature modifier and tags it for the Blender sculpt stage. Existing painted weights are NEVER overwritten. Unmatched or ambiguous muscles are left unchanged; keep author control over anatomical placement. Manual weight painting at shoulders, elbows and tendon insertions is REQUIRED for convincing results.

## Flex and Stretch clips

`scripts/blender_sculpt_bridge.py` generates two separate **vertex-level** blend shapes per recognized muscle: `ANATOMY_FLEX` bulges the midsection and shortens it slightly, and `ANATOMY_STRETCH` slims/lengthens it. Local attachment endpoints remain fixed; this is not global model scaling or 2D sprite deformation. Original 12-vertex muscle rings use their own centerlines. Other custom meshes use a conservative dominant-axis fallback and should be inspected.

Muscle-specific bone-target mapping connects deformations to the pose bones. The script samples original armature NLA strips to create matching **named NLA shape-key clips**, then exports glTF `export_animation_mode='NLA_TRACKS'`, `export_morph=True`, `export_skins=True`. Blender drivers alone are not portable to Three.js; sampling to morph keyframes is therefore essential.

`--workbench-copies` adds a hidden `SCULPT_WORKBENCH_NON_EXPORT` collection of high-subdivision copies. They are editable high-resolution references; the game GLB excludes them. For production sculpting, edit the high-res copy, bake detail to normal textures on the low-poly deformation cage, then validate the complete exported animation (Blender and Three.js). Do not call these copies baked game geometry.

## Hard restrictions

- Preserve the monster's exact reference identity; MPFB donor is NEVER the game character.
- Corrective shape keys are stylized contractility, NOT anatomical muscle tissue simulation or full FEM.
- Never export Z-Anatomy commercial-use-restricted reference geometry by accident.
- Never claim exact human tendon attachments from the single reference drawing.
- The Blender 4.5 stage requires a real working bpy runtime. If binary or addons missing, clearly report missing dependency rather than fabricate animated output.
- Do not mark a GLB visually confirmed until opened and animated in Blender/Three.js.
