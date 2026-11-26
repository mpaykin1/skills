---
name: sprite-stacking-primary
description: Mandatory primary sprite stacking mode for ALL future META GAME FUSION game builds. Prioritize real volume RGBA slice stacks for props, architecture detail, vehicles and coherent multi-pose NPC/hero art; preserve Rapier/Recast physical truth and approved artistic identity.
---
# SPRITE STACKING PRIMARY — META GAME FUSION

Whenever creating/modifying a game with META GAME FUSION:

1. The maximum feasible amount of **visible 3D graphics** must use **genuine sprite stacking**: carefully aligned transparent PNG XY cross-sections of one physical 3D volume, at multiple heights, viewed as a 3D volume in Three.js. Mandatory `src/sprite-stacking.js` and `world.sprite_stacking.primary_renderer=true` for new game projects.
2. Priority: **buildings/exterior details, interior furnishings, vegetation, rubble, machinery, weapons, vehicles, pickups, monsters, characters** if and only if coherent approved slice volumes exist; keep large navigable planar floors and solid transparent physically collision objects as true CSG/Manifold geometry when needed.
3. **Original artwork identity remains inviolable**: never substitute user-approved GIF/PNG characters with generated geometry; don't swap characters across frames, directions, idle/attack; don't flatten GLB rigs without complete approved poses. For buildings from painted PNG, obey PNG multiview: front/rear/left/right/roof actual authored art, then valid multi-view slice volume.
4. Use `scripts/sprite_stack_bridge.py` for genuine alpha-layer packing and 4 actual-volume-derived horizon projections, `scripts/glb_to_sprite_stack.py` for authorized watertight static GLBs, with SHA-256 and source rights. Reject flat front-view extrusion falsely presented as full 3D. No generic grids, repeating textures, voxel-block cubes or arbitrary 2D cheats.
5. One consistent world pivot/scale, transparent alpha, depth writing and testable front/side/rear/top views. Animated organic actors use complete multi-pose stacks; no CSS deformation, automatic player action or unrelated poses.
6. Rapier owns fixed/dynamic collision, Recast owns walkable NavMesh, MeshBVH indexes *actual solid geometry*, YUKA+XState owns NPC decisions, bitECS owns event sync. Sprite planes are decorative, not physical colliders or NPC route blockers. Do not lose animation when turning or changing quality.
7. Use geometric batching/LOD and mobile portrait/landscape 100dvh. Validate actual frames at eight yaw angles and strict edge-on; if no real browser check, explicitly mark unverified. No fake public game link.
8. Follow `skills://plugins/sprite-stacking-grunge/sprite-stacking-grunge/skill.md` and **mandatory** `../animated-world-guard/SKILL.md` plus `../png-multiview-meta-game-fusion/SKILL.md` whenever architecture comes from a painting.

Implementation details: `skills/meta-game-fusion/references/sprite-stacking-integration.md`.
