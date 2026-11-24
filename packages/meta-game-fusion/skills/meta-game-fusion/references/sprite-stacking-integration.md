# META GAME FUSION 2.4 — sprite stacking as PRIMARY visual system

## Invariant

Build the maximum possible **visible world** with *real* sprite stacking: physical RGBA horizontal slices of a coherent 3D volume, each aligned on one pivot and one world scale. **Not** stacked duplicates of one flat painting, a GIF impostor, a row of PNG stripes, a billboard standing in for a volume, or a fake series of rotated screenshots. Preserve model identity in every animation state.

The skill inherits the requirements of `skills://plugins/sprite-stacking-grunge/sprite-stacking-grunge/skill.md`, mandatory `../animated-world-guard/SKILL.md`, and `../png-multiview-meta-game-fusion/SKILL.md` when architecture comes from an approved PNG painting.

### Coverage priority

1. **Sprite stacking first:** original/new prop volumes, ruined masonry facades, vegetation, rocks, furniture, machinery, weapons, vehicles, pickups, torches, lanterns, scene decorations, dynamic rigid props, monsters and NPCs *when complete same-identity pose stacks are available*.
2. **Geometry retained:** physically authoritative Rapier colliders, Manifold/three-bvh-csg solid cutouts, static platform walkable surface and real Recast NavMesh. MeshBVH handles solid occlusion and selection, *not* alpha-sliced decorative quads. Never replace the navigable passage with a purely painted arch.
3. **Approved media never silently replaced:** user-approved PNG/GIF characters and vehicles stay unchanged until coherent, approved 3D cross-section stacks exist. Imported GLBs retain animated rig/clip data unless the owner explicitly approves a full pose-based replacement. Non-volumetric sky/fog, PBR terrain, screen-space postprocessing and Quarks particles are exempt.
4. **No source alteration:** ScanCode/ownership, exact hashes and individual reuse approval precede pack construction. The new project is outside original sources. No animation-state character changes.

### Code locations

- `scripts/sprite_stack_bridge.py`: rigorous `stack.json`/RG​BA PNG slice validation, real per-layer atlas compiler with SHA-256, low-angle orthographic profile projections **computed from the same slices**, no repainting. `original-concept` builds genuine analytic volumes of rocks, arches, columns, trees, lanterns, crates, hero and two NPCs. Its outputs are already bundled in `templates/rapier-world/public/sprite-stacks/` (12 original asset families; animated walk/idle/jump/investigate pose stacks).
- `scripts/glb_to_sprite_stack.py`: optional `trimesh` voxelization of a SHA-pinned, expressly approved **watertight/static** GLB into real aligned RGBA source slices; refuses skin, morph, animation, holes, invalid bounds. Nearest-vertex color/UV sampling is only a **preview** and requires artist acceptance. No fake exact UV claim. The converted original GLB remains untouched.
- `templates/rapier-world/src/sprite-stacking.js`: actual Three.js horizontal XZ quads per slice, one combined BufferGeometry/draw call per stack, cutout alpha with depth write, instanced batches for large scenery, hash-verified binary atlases, pose animation linked only to proper actor events. For **nearly edge-on** views, 4 side projections are calculated from the *same* physical slices; never substitute unrelated 2D artwork. User art loaded by HTTPS/localhost SHA-256.
- `templates/rapier-world/src/living-world.js`: visible rubble/trees/lanterns replaced with stacked volumetric assets, independently illuminated and animated.
- `templates/rapier-world/src/main.js`: world-first render choice, 3D physics retained, decorative replacements in stages and distance, sprite-stacked dynamical crates with unchanged Rapier bodies; authored concept hero and two NPC bodies use complete matching animated pose stacks. Existing approved external actor art is left alone.
- `scripts/fusion_builder.py`: default mandatory `world.sprite_stacking.primary_renderer=true` with hash of `/sprite-stacks/manifest.json`. Option `--sprite-stack-source APPROVED_ROOT` merges independent source stacks; no missing textures or silent fallback.

### Accepted original layered sprites

Use `<root>/<asset-id>/stack.json` and `<root>/<asset-id>/layers/000.png ... 071.png`. All slices are square RGBA, identical pixels, same 3D camera-space origin, **bottom to top**. User's other Sprite Stacking Grunge Horror plugin schema `{"layers":["layers/000.png",...],"spacing":[dx,dy,dz],"pivot":[x,y,z],"size":384}` is accepted for layout, with an additional explicit `"approved_for_reuse":true` and `"license":"proprietary-user-owned"` (or rights-reviewed compatible license). 3D Three.js axes are right X, up Y, forward Z; PNG row top is +Z. Preserve provenance, hashes, geometry source, original colors/hand-painted textures, local volume shape and thickness.

Animated clips: each independently authored full volume state is at `<asset-id>/actions/<action>/000/layers/000.png ...`. Full action frame sequences must have the same number of slices, cell dimensions, pivot, shape identity and consistent material lighting. Do not stretch, interpolate, mirror or swap the hero to fake animation. Validate authored idle, walk, run, jump, attack and turn where actually required by the gameplay. An optional directional 4-way low-angle atlas is derived from the same physical slices, not hand-drawn unrelated perspectives.

### Commands

```bash
# Runtime already includes bundled original concept stacks (no Pillow required):
python skills/meta-game-fusion/scripts/fusion_builder.py build \
  --library /path/to/approved-library --concept 'Fog-bound viaduct' \
  --out /path/to/NEW-game

# Optional tools, offline, no borrowed art:
python -m pip install -r skills/meta-game-fusion/requirements-sprite-stacking.txt

# Pack user-approved consistent volume slices:
python skills/meta-game-fusion/scripts/sprite_stack_bridge.py bake \
  --source /path/to/approved-volume-slices --out /path/to/NEW-atlases

# Convert a personally approved static watertight GLB to preview slices,
# after verifying exact source hash; review color fidelity before using:
python skills/meta-game-fusion/scripts/glb_to_sprite_stack.py \
  --glb /path/to/model.glb --source-sha256 HEX64 \
  --id ruined-machine --license proprietary-user-owned --approved \
  --out /path/to/NEW-source-slices

# Build while merging the approved volume slices, without overwriting defaults:
python skills/meta-game-fusion/scripts/fusion_builder.py build \
  --library /path/to/approved-library --concept 'Fog-bound viaduct' \
  --sprite-stack-source /path/to/approved-volume-slices \
  --out /path/to/NEW-game
```

### Quality gates

- Source hash, atlas hash and frame/low-angle-view hashes must all match. Abort on missing PNG, unsafe folder, bad alpha, nonfinite scale, incomplete poses, unsupported license, or animation identity drift. A sprite GIF that only looks like an animated flat billboard does not satisfy this integration.
- Technical 360 yaw and 8 principal directions need on-screen review. Nearly-horizontal viewport derives real projections, **but this is not a substitute for testing the artistic result**. If authored source is only a single front PNG, stop and build approved rear/side/roof sources via multiview rule, never pretend hidden geometry was recovered.
- Use mobile instancing/LOD, keep GPU budget bounded, no source-derived repeating texture patterns, no global deformation/oscillation substituting real animations. Verify 390×844 and 844×390 with real browser frames; if not observed, status `browser-unverified`.
- No auto hero input, no bypass of Recast/Rapier, no invisible/phantom colliders, no claimed hosted URL without a deployment.
