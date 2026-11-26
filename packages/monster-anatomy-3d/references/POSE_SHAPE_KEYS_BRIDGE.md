# Blender Studio Pose Shape Keys 1.0.0 → Monster Anatomy 3D

Official extension: https://extensions.blender.org/add-ons/pose-shape-keys/versions/
Official source: https://projects.blender.org/studio/blender-studio-tools/src/branch/main/scripts-blender/addons/pose_shape_keys
License: GPL-3.0-or-later. The Monster Anatomy ZIP **does not bundle** Blender Studio's extension code; use the installer to obtain the official 1.0.0 package. The addon requires Blender 4.2–4.5 for v1.0.0. The newer 1.1.1 needs Blender 5.0+, and must NOT be installed in this Blender 4.5 project.

## Purpose

Preserve already-sculpted anatomy while changing Rigger IK/FK, weights and deformation constraints. Pose Shape Keys stores the evaluated mesh at an action frame, the artist sculpts the correction, and the addon pushes the sculpt into the correct shape keys without destructive applying of the armature. This is **pose-space sculpt authoring**, NOT an anatomical AI generator nor a finite-element muscle solver.

## Get the real upstream

On a networked machine run:

```
python scripts/download_pose_shape_keys.py --dest vendor/pose-shape-keys
```

The downloader reads the official Blender Extensions dynamic repository index for Blender 4.5.0, selects `pose_shape_keys` **1.0.0**, requires the index SHA-256, checks the manifest ID/version/license/compatible Blender range, and extracts the original GPL addon to `vendor/pose-shape-keys/pose_shape_keys`. No forked package is substituted. When behind a firewall, download 1.0.0 from the official version-history page and use `--zip path/to/official.zip` for local verification and extraction. No contents are fetched from third-party mirrors.

## Anatomical authoring bridge

```
python scripts/build_with_anatomy.py --blender blender --pose-shape-keys
```

This **optional** stage executes AFTER mesh-detail generation, Instant Meshes retopology and optional Rigger control generation. It creates a new editable `monster_pose_key_authoring.blend` and an index `monster_pose_key_authoring_pose_keys.json`. The original `monster_blender_sculpt_ready.blend`, skeleton `MONSTER_RIG`, Rigger-compatible bone names, GLB, materials, UV, existing actions/NLA, `ANATOMY_FLEX`/`ANATOMY_STRETCH`, and muscle vertices/weights are preserved. Output contains addon-native `Mesh.pose_keys` entries for existing muscle shapes, with the action/frame at strongest matching muscle-bone activation from the ATTACK animation. These are **workbench registrations**, not finished corrective sculpts.

For an existing scene:

```
blender --background --python scripts/pose_shape_keys_monster.py -- \
  --blend monster_blender_sculpt_ready.blend \
  --output-blend monster_pose_key_authoring.blend \
  --addon-dir vendor/pose-shape-keys --track ATTACK
```

## Finish the sculpts in Blender

1. Open the generated `monster_pose_key_authoring.blend` in Blender 4.5 with Pose Shape Keys 1.0.0 enabled (the downloader gives you the exact extension directory).
2. Select one of the muscle meshes with an `ANATOMY_FLEX` pose key. Use **Set Pose → Store Evaluated Mesh** to create a non-destructive stored pose sculpt. Modify the stored mesh in Sculpt Mode, preserving volume over the elbow/shoulder/knee and rechecking the reference silhouette.
3. Use **Overwrite/Push Shape Keys** to transfer the sculpted correction into the existing `ANATOMY_FLEX` target. Keep the `ANATOMY_STRETCH` morph and original vertices as authored until intentionally revised.
4. Do not blindly install live driver expressions for game glTF. Blender drivers and addon metadata are not exported as standalone glTF animations: **bake final shape key values into the corresponding named NLA clips** before game GLB export. Existing `blender_sculpt_bridge.py` produces shape-key NLA and `rigger_monster_blender.py` keeps them with retargeted actions; after manual sculpts, re-export and inspect the actual morph target displacement for each clip.

## Constraints

- Never silently replace user-approved monster with an MPFB donor; only muscle meshes on `MONSTER_RIG` are edited.
- Original `.blend` is immutable; auto-created pose keys do not make unpainted muscles anatomically correct.
- For the v0.7 retopology stage, pose correctives need the FINAL vertex topology. Sculpt after retopology and avoid re-topologizing the authoring mesh without deliberate transfer.
- `--rigger-controls` creates an animator-only IK/FK `.blend` **before** these authoring hooks. Rigger's Preserve mode must not rename bones or mutate the original muscle geometry.
- The installed upstream binary/addon **has not been executed in this ChatGPT container** because Blender and network access are unavailable. Do not claim Blender gameplay/export verification.
