# ManifoldCAD 3.5.1 × three-bvh-csg 0.0.18 — robust architecture

Upstream: https://github.com/elalish/manifold ; `manifold-3d@3.5.5` (Apache-2.0). License and notice: `vendor/manifold-3d/`. The JS/WASM package is an external pinned npm dependency, **not bundled**. The previously installed `three-bvh-csg@0.0.18` remains available for older worlds.

## Linked pipeline

- `fusion_builder.py` consumes the **same** checked and bounded portal recipe as `csg_bridge.py` and selects `world.csg_architecture.backend = "manifold-3d@3.5.5"` for newly built worlds. Old worlds with absent backend still run using the previous `three-bvh-csg` class, unchanged.
- `manifold-architecture.js` lazily loads `manifold-3d` WASM, builds a *closed* box, subtracts a below-ground rectangular doorway and a Z-axis circular vault, and exports an indexed, validated Three.js BufferGeometry. It uses Manifold's native `cube`, `cylinder`, `translate` and `difference` API. All Manifold solid/mesh objects are explicitly freed after copy-out.
- Result topology is checked for degenerate triangles, invalid indices, non-finite coordinates and open/nonmanifold edges. A validation error **halts the world bootstrap** instead of substituting a fake portal. The same validated Three.js mesh is passed to the existing authoritative Rapier static triangle collider and registered with MeshBVH for visual picking and LOS. The player and guide both use Rapier body movement; Recast keeps its existing walkable-floor/obstacle pathfinding, never automatically imports raw CSG as a NavMesh.
- Qdrant indexes the authored Manifold adapter based on the real bundled script's SHA-256. The exporter never applies CSG to an imported skinned, morphing, animated or unapproved GLB. Source files in `meta6` and other source repos stay read-only.
- The deep fog, drifting particles, lanterns, scenery and the guide NPC continue via `living-world.js`, `navigation.js` and `postfx.js`. The authored hero remains input-controlled, never animated by this static-architecture module.

## Usage

```bash
python skills/meta-game-fusion/scripts/fusion_builder.py build \
  --library /path/to/library --concept 'Город под водой' --visual-style nocturne \
  --out /path/to/new-world
cd /path/to/new-world
npm install --ignore-scripts
npm run dev
```

The JSON plan declares the Manifold backend. Requires npm installation and WASM-capable browser. This archive contains code, plans and notices, **not a working compiled WASM asset, rendered video or public game deployment**. Treat any unverified browser preview as a prototype, not a completed game.

### Why both engines?

- **three-bvh-csg** is fast and offers convenient direct Three.js brush editing; use it for approved legacy worlds and simple booleans.
- **Manifold** is used for new original closed architectural solids to avoid the edge-case open/invalid topology sometimes produced by three-bvh-csg. The **Manifold backend fails closed** if WASM is missing or its output invalid, not silent fallback to visually similar but physically wrong meshes.

Manifold is not a renderer or animation system. It never substitutes approved art, model rigs or textures and does not itself make a finished level. Preserve the obligatory `animated-world-guard` and rights checks.
