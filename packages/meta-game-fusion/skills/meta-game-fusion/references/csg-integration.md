# three-bvh-csg — linked procedural architecture (v1.4)

This feature uses `three-bvh-csg@0.0.18` with `three@0.186.1` and `three-mesh-bvh@0.9.18`. Source: https://github.com/gkjohnson/three-bvh-csg ; verified MIT license stored at `vendor/three-bvh-csg/LICENSE`.

## Combined workflow

1. `fusion_builder.py build` consumes a checked Rete blueprint or an original concept and creates `world.csg_architecture` via `scripts/csg_bridge.py`. Each stage gets a reproducible original Gothic portal, with the marker position and its chapter palette. Imported GLBs remain unchanged and are **never** converted to CSG automatically.
2. `src/csg-architecture.js` creates closed primitive brushes and computes a wall minus a rectangular door minus a cylinder vault with `Evaluator.evaluate(..., SUBTRACTION)`. No placeholder geometry or fake openings: the cutout is an actual hole in the resulting triangle mesh.
3. The **same** resultant triangle mesh is sent to `FusionPhysics.addCSGTrimesh()` as a static Rapier collider and indexed by `FusionSpatialBVH.register()` for Three raycasting/picking and NPC line-of-sight. Character animation and input handling are untouched.
4. The opening width is at least 10.7m and the outer piers are outside the Recast walkable corridor. Recast remains the exclusive path planner for NPCs, based on the Rapier floor/obstacle plan. Do not claim arbitrary carved top surfaces become automatically navigable.
5. Postprocessing and the living-world system add independent animated atmospheric layers; structural CSG meshes remain immobile. Story stages come from Rete.js / inkjs. Qdrant indexes the authored CSG adapter with real bundled SHA-256.
6. ScanCode rights + explicit asset approvals remain mandatory for *imported* code and GLBs. Original procedural brushes do not grant any rights to external models.

## Build

```bash
python skills/meta-game-fusion/scripts/fusion_builder.py build \
  --library /path/to/fusion-library \
  --concept 'Разрушенный город за арочным мостом' \
  --visual-style ink --seed 147 \
  --out /path/to/new-world
cd /path/to/new-world
npm install --ignore-scripts
npm run dev
```

The world JSON includes `csg_architecture` with a finite, bounded recipe; runtime scene creation computes the actual geometry. The original source project remains read-only. A plain `rapier_bridge.prepare` output without an architecture plan still runs in legacy mode without CSG.

## Boundaries

The upstream project warns about numerical precision and potentially non-manifold output for difficult booleans. Only closed primitive brushes are used here; bounds, triangle counts, indices and all vertex coordinates are checked before Rapier receives geometry. This is **not** a general watertightness guarantee. Never advertise a browser PASS without executing a real build and watching rendered frames. No binary is bundled; the npm package must be available. Existing hero/other NPC animations must pass `animated-world-guard` unchanged.
