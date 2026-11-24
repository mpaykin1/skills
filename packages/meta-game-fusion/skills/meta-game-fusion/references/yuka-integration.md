# YUKA 0.7.8 × META GAME FUSION 2.0

- Source: https://github.com/Mugen87/yuka, MIT, master `10591304811222d6856020d5de129b39ef43b58d` (2023-01-16), npm `yuka@0.7.8`. Full upstream code NOT bundled; only authored adapters and upstream MIT notice. Install actual npm dependencies in a generated game to render and run. No CDN or unexplained fetched textures.
- `scripts/yuka_bridge.py` creates a bounded `world.npc_ai` plan from the same Rete/Ink chapter node IDs and style names. The original idea and existing game source directories are immutable.
- `src/ai-yuka.js`: 1 existing Recast Scout (`physics.guide`) + 2 original articulated sentinel NPCs. YUKA `Vehicle`, `Path`, `FollowPathBehavior` generate smoothed desired velocities at 60 Hz. YUKA is an **intent / steering layer**, not a physics world, and does not own final positions. Recast's `NavMeshQuery.computePath` provides EVERY actual patrol/guide/investigation route. If Recast cannot find a path, the agent stops safely, it does not cut through a wall or walk in a straight line to the target.
- `src/physics-world.js`: 2 new Rapier kinematic-position capsules and controllers for sentinels; all visuals follow their real `RigidBody.translation()` after `World.step`. The original single player capsule, movement, input, identity, jumps, actions and speed remain unchanged. No external game code is executed.
- NPC patrol route repeats independently. On a **genuine player interaction**, nearby NPCs with MeshBVH line of sight may investigate the signal, using a fresh Recast path; afterwards they resume patrol. Stage changes recolor their authored lanterns, alter patrol pace and animate head/arms/torso. No autonomous player action, teleport, or unapproved character replacement.
- Fixed budgets: 2 sentinel patrols + 1 scout, maximum 24 Rete scene cues. CPU-side YUKA updates only during physics ticks; one render pass via existing Postprocessing pipeline; three.quarks remains a bounded separate particles pass. No new GPU or network requirement beyond normal WebGL.
- The YUKA adapter is source-hashed for Qdrant engine-component search. ScanCode and Khronos GLB Validator still gate any imported GLB. The original new sentinel art is procedural and does not replace approved user images or existing characters; any future reuse of user art still requires approved multiview files/animation.
- The active Recast Scout and patrols must be visibly animated. If Recast/YUKA npm dependency is absent or a patrol cannot initialize, mark the browser result incomplete instead of claiming successful game verification. Use Playwright to check observable sentinel displacement and preservation of player inaction at desktop and mobile viewports. No public game URL exists until a real deploy.

```
python skills/meta-game-fusion/scripts/fusion_builder.py build --library /scratch/approved-lib --concept 'Забытая станция' --out /scratch/three-game
python skills/meta-game-fusion/scripts/yuka_bridge.py inspect --world /scratch/three-game/public/world.json
# In the generated game after npm dependencies have been installed:
npm run dev
```
