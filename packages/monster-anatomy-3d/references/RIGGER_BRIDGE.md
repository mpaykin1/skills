# Rigger × Monster Anatomy 3D (seventh open-source component)

**Official upstream:** https://github.com/asu37/Rigger

**Pinned revision:** `c8f1d1b9a8729582c61fa0ffa9a658ec4f4f6e77` (Rigger v1.2.0; Blender 4.2+). **License:** GPL-3.0-or-later for the upstream Blender add-on (no upstream code bundled). `scripts/download_rigger.py` checks out and verifies exact revision. The bridge is newly written independently and invokes Rigger's public Python functions directly; do not describe the bridge as a copy of its entire implementation.

**Why it reinforces previous components**

- **MPFB2** provides the 17-bone donor-to-monster correspondence. `MPFB_TO_MONSTER_BONE_MAP.json` is a ready explicit mapping when the animation source uses the MPFB `game_engine` rig. It is *not* valid for arbitrary FBX/GLB sources without matching bone names.
- **Z-Anatomy** supplies origin/insertion anchors; **MyoGeneratorRemix** generates deforming muscle meshes already weighted to `MONSTER_RIG` via `myo_rig_bridge.py`.
- **Blender** retains its flex/stretch NLA morphs for muscles; Rigger's new retargeted clip creates a matching morph clip using the real animated bone angles (not separate image deformation).
- **Instant Meshes** produces skin-weighted LOD meshes; the same `MONSTER_RIG` and bone names remain usable by Rigger. Thus run Rigger **after** any retopology stage.
- **TRELLIS.2** contributes a static reference shape. Do not feed TRELLIS static surface as a motion skeleton or replace the original approved creature.

**Acquire the actual source (network, Git, Blender):**

```sh
python scripts/download_rigger.py --dest vendor/Rigger
```

**Create preserved animator-friendly controllers on the monster, in a new .blend file:**

```sh
python scripts/build_with_anatomy.py --blender blender --rigger-controls
```

This calls official `quick_rig.fill_limbs` + `quick_rig.quick_rig` with `settings.mode='PRESERVE'`; it refuses `CONVERT`, never renames the original `MONSTER_RIG`, and never overwrites the input scene. Rigger must be able to infer at least one safe limb chain. For exotic rigs where automatic guessing fails, customize the reference anatomy manually in Rigger rather than silently replacing the character.

**Retarget a real FBX or GLB motion source to the original monster, with muscle flex tracks:**

```sh
python scripts/build_with_anatomy.py --blender blender --rigger-motion walking.glb --rigger-clip WALK_FROM_RIGGER
```

For motion made on MPFB's `game_engine` rig:

```sh
python scripts/build_with_anatomy.py --blender blender --rigger-motion mpfb_walk.glb --rigger-bone-map references/MPFB_TO_MONSTER_BONE_MAP.json --rigger-clip WALK_MPFBRIG
```

If the source action is ambiguous, supply `--rigger-motion-action` and optionally `--rigger-motion-rig`; `--rigger-in-place` suppresses root travel for a stationary loop. Explicit bone map keys are **source bones** and values are **MONSTER_RIG bones**. Never silently invent mappings for unusual monsters.

**Run on an existing three/five/six-way Blender scene instead of rebuilding everything:**

```sh
python scripts/rigger_monster_worker.py --mode retarget --blender blender --rigger-dir vendor/Rigger --blend build/monster/monster_blender_sculpt_ready.blend --motion walking.glb --output-glb build/monster/monster_rigger_walk.glb --clip WALK_FROM_RIGGER
```

**Export an existing true Rigger control rig to game GLB** (optional, separate from direct monster GLB export):

```sh
python scripts/rigger_monster_worker.py --mode export --blender blender --rigger-dir vendor/Rigger --blend build/monster/monster_Rigger_IKFK_controls.blend --output-glb build/monster/monster_Rigger_game.glb
```

**Hard protections:** Never replace the original monster with a humanoid. Do not export MPFB donor or Z-Anatomy reference models as monster art. Preserve original mesh vertex coordinates, topology, UVs, materials, skin vertex weights, muscle corrective shape coordinates, NLA clip names and bone names. New animations must get unique names; preserve existing idle/stalk/attack clips. Rigger may alter controller scene hierarchy but must leave game skeleton unchanged. New actions are authored in a copy. Rigger's optional face/video tracking is not used by this bridge. Only claim Blender runtime success after actual execution and output inspection.

**No internet/GPU in this environment:** This skill includes the source installer and actual API bridge. Upstream Rigger checkout and Blender executable are external dependencies. If fetching fails, no action has been applied to the monster and no GLB is claimed.
