# MyoGeneratorRemix integration — source-verified

**Project:** https://github.com/MiguelDLM/MyoGeneratorRemix

**Pinned source:** `v2.0.0` (stable release listed June 24, 2026); upstream has pre-release versions that may differ. Pin to avoid silent API changes. The repository README and `AddonFolder` sources were inspected on 2026-11-22.

**License:** README states GNU GPL version 3 or later; repository LICENSE.md points to GPL 3.0. Current main blender_manifest.toml separately lists GPL-2.0-or-later; preserve the upstream notices and verify the chosen release before redistribution. Copy original notices when redistributing source. Blender outputs may have different ownership, but do not claim a definitive legal conclusion.

## Installation
Run `python scripts/download_myogenerator.py --dest vendor` with internet access; install `vendor/MyoGeneratorRemix-v2.0.0-blender-addon.zip` through Blender preferences. Requires Blender >= 4.2 (source blender_manifest.toml), developed on 4.4.x.

## Actual addon UI sequence
1. Prepare closed clean bone meshes with realistic dimensions and nonintersecting surfaces; unit scales consistent.
2. Sidebar N → `MyoGeneratorRemix` tab; set data folder, filename and unique muscle name; Submit Muscle.
3. Under **Origin Creation**, select originating bone, Start Origin Selection, lasso *contiguous faces*, Submit Origin.
4. Under **Insertion Creation**, select insertion bone, Start Insertion Selection, select contiguous faces, Submit Insertion.
5. Under **Muscle Creation**, Create Muscle Path; edit the Bezier curve handles and radii so the belly follows the correct line of pull and does not penetrate surrounding bones.
6. Preview Muscle; adjust subdivision/contour resolution and connection mode and regenerate; generate final muscle mesh.
7. Calculate measurements/CSV when needed. Repeat muscles individually.
8. The add-on's procedural material can show fiber texture with subsurface scattering; bake or replace this material for real-time Three.js because Blender node graphs do not always export to glTF.

## What upstream does not do
- Does not automatically recover hidden anatomy from an image.
- Does not generate a complete art-directed creature or full animation set from one prompt.
- Produces volume meshes; skinning to rig and corrective deformers require a separate rigging pipeline.
- Anatomically sound attachment locations must be provided by an artist / procedural anatomy specification.

## Muscle attachment plan for reference monster
Back hump: broad trapezius and latissimus-like sheet under scapula with thick neck attachment; shoulder: deltoid and rotator analog; chest: pectoral; upper arm: thin biceps/triceps; forearm: long flexor-extensor/tendon bundles; abdomen: attenuated external obliques and abdominal wall; thigh: irregular quadriceps/hamstrings; calf: gastrocnemius/soleus-like, Achilles into heel; fingers: long superficial and deep flexor tendons.
