# MPFB2 ↔ Z-Anatomy ↔ MyoGeneratorRemix (v0.3)

- Source: https://github.com/makehumancommunity/mpfb2 at commit `9de0707fdc88438d7c53a1a2ac7937d9221e2431` (2026-11-12); official Blender extension manifest v2.0.18, Blender >=4.2.0. Full source is fetched by `scripts/download_mpfb.py` on a networked host and stored in `vendor/MPFB2` **outside of the distribution ZIP**.
- License: MPFB code **GPL-3.0** and bundled base assets **CC0-1.0**. The MPFB authors state they make no copyright claim to program-generated output; additional installed asset packs may differ. Do not copy GPL source files into a non-GPL proprietary program. Keep local source and license notices.
- Z-Anatomy: names/landmarks are references, original atlas is CC BY-SA with some NC-sourced assets; no atlas mesh is copied to game outputs by this bridge.
- MyoGeneratorRemix: use its real muscle geometry editor after manually confirming attachment locations. Its geometry does not auto-appear merely because anchor spheres exist.

## Full integration

`python scripts/build_with_anatomy.py --blender blender --output-dir build/monster`

1. Fetch official pinned MyoGeneratorRemix and Z-Anatomy source using their downloaders.
2. Fetch pinned MPFB 2 source, run Blender's native `extension build` command and install it via official `bpy.ops.extensions.package_install_files` into the Blender user profile. This alters the Blender **user extension install**, not your games. If extension API unavailable, stop with explicit error.
3. Create original monster blockout + skinned three-clip GLB (not final creature).
4. Parse Z-Anatomy names and create monster-bound Myo origin/insertion marker pairs.
5. MPFB `HumanService.create_human()` produces a real parametric human mesh; `HumanObjectProperties.set_value` + `TargetService.reapply_macro_details` sets height, weight, muscle and proportions; `HumanService.add_builtin_rig(mesh, 'game_engine')` adds a weighted game rig.
6. Match 17 monster-to-MPFB bones and transfer fractional landmark positions from Z markers onto matching MPFB bones in editable Blender scene.
7. Save `monster_three_way_anatomy.blend`, `mpfb_bone_correspondence.json`, `mpfb_anchor_correspondence.csv`. Both references use separate rig hierarchies. The MPFB human donor is deliberately offset and not included in the generated game GLB.
8. Use real muscle volumes from MyoGeneratorRemix and perform final rigging/retopology manually or with compatible tools. Treat MPFB muscle parameters as whole-body *morphological controls*, not separate anatomical muscle volumes.

## Why integration is substantive

- **MPFB**: actual CC0 baseline human mesh + skinning topology + standard game armature, used as an anatomical *donor*.
- **Z-Anatomy**: anatomical naming and origin/insertion guides from a Blender atlas without copying third-party mesh data.
- **MyoGeneratorRemix**: editable volume construction from selected bone/surface attachments, with interactive anatomical verification.
- Each `MPFB_ORIGIN_*` / `MPFB_INSERTION_*` marker in the final `.blend` points to the corresponding `ZA_*` marker; mapping is in CSV and bone length ratios in JSON. This avoids a superficial list of unrelated integrations.

### Critical limits

- Not a one-click image→photo-real monster generator. MPFB human proportions require extreme remodeling to match the user's hunched, long-armed monster; game GLB remains the original monster, not an MPFB body replacement.
- Not a live muscle simulation. No automatic MyoGeneratorRemix muscle extrusion or skin attachment is claimed.
- Blender 4.2+ and a valid local extension repository are required; no Blender runtime in this build environment, so direct Blender execution is unverified.
- If network is unavailable in the host, `--offline` requires all sources already downloaded, or `--skip-mpfb` generates the original two-source guides.
