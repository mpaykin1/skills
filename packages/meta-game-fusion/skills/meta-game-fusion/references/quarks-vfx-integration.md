# three.quarks — atmospheric GPU-batched scene effects (v1.9.0)

- Upstream: https://github.com/Alchemist0823/three.quarks
- NPM pinned: `three.quarks@0.18.0`, `quarks.core@0.18.0`
- License: MIT — Copyright (c) 2019 Forrest Sun
- Compatibility: Three.js@0.186.1 satisfies upstream >=0.182.0.
- Bundled: authored adapters and license notices only. **Upstream NPM code not bundled, not installed, browser render not verified.**

## Synergy with other open-source modules

1. `fusion_builder.py` derives deterministic VFX `scene_cues` from approved Rete.js scene nodes, Ink narrative stages and marker geometry. No new story logic is executed.
2. `vfx-quarks.js` owns **one** `BatchedRenderer`, and **three bounded particle systems** (64 mist, 112 ash, 70 luminous rune motes). It does not create duplicate render loops or extra draw calls for every particle; updates once before `FusionPostFX.render(dt)`.
3. Colors adapt to the established Postprocessing profiles: nocturne, ink, ember, horror, dream, pixel. PostFX mode `cinema` gives full emission, `eco` caps emissions to 35%, `off` disables VFX rendering. Runtime maximum is 246 particles; no unbounded spawns.
4. Rapier owns hitboxes and motion; Recast owns NavMesh and guide navigation; MeshBVH owns static geometry queries. Quarks emits no player movement, collision, damage or path commands.
5. Motes use a generated 32×32 RGBA soft texture in a `THREE.DataTexture` — no CDN requests, no unapproved asset downloads or replacement of user-provided sprites. Existing verified imported 3D models are unaffected.
6. Qdrant indexes authored VFX adapter with its SHA-256, and ScanCode + Khronos Validator remain mandatory for any imported third-party media. The runtime adapter does not waive asset rights.
7. The animated-world guard remains mandatory: particles are atmosphere, **not a substitute for full NPC walk/idle/gesture animations**. Both mobile viewport orientations remain supported.

## Usage

```bash
python skills/meta-game-fusion/scripts/fusion_builder.py build \
  --library /path/to/approved-library --out /new/target/world \
  --concept 'Мост сквозь пепел' --visual-style ember
cd /new/target/world
npm install
npm run dev
```

`world.json` includes `particle_fx` created through `quarks_bridge.make_plan(world)`. To repair metadata only for a **generated** game:

```bash
python skills/meta-game-fusion/scripts/quarks_bridge.py configure --project /new/target/world
```

Dependency installation and browser validation require an environment with npm registry access. Until verified, generated game is source-only preview, not a working published link.
