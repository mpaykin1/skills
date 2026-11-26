# bitECS 0.4.0 — единая ECS-шина игрового мира

Upstream: https://github.com/NateTheGreatt/bitECS (MPL-2.0), npm `bitecs@0.4.0`.
The package is not bundled: install the pinned dependency in a generated game.
A copy of the unchanged upstream MPL-2.0 license is shipped at `vendor/bitecs/LICENSE`.
Source code for the external MPL-licensed dependency is published at the upstream
repository and through its npm distribution; preserve the dependency's license and
provide its corresponding upstream source to recipients if distributing executable bundles.

## Actual integration

- `scripts/ecs_bridge.py`: validates the bounded Rete/Ink stage graph, builds the
  immutable engine authority contract and inspects generated game packages.
- `templates/rapier-world/src/ecs-runtime.js`: uses real `createWorld`,
  `addEntity`, `addComponent`, `query` APIs from bitECS. Four actors: the
  player, Recast scout, and two YUKA sentinels. The spatial `Position` and
  `Velocity` components are read-only *snapshots* of real Rapier results.
- System event stream has only four types: `scene:enter`, `player:interact`,
  `dialogue:state`, `quality:mode`. No arbitrary code execution, user-input
  injection, NPC control of player or importing strangers' game mechanics.
- Scene events orchestrate `livingWorld.enter`, `Quarks.enter`,
  `YUKA.enter`, `Howler.enter`, and `PostFX.setMood`. Ink dialogue state ducks
  Howler. User E-interaction dispatches Quarks pulse, Howler positional sound,
  and YUKA investigate signal. Eco/off changes send one quality event.
- `query(world, [Position, Sentinel, AudioEmitter])` feeds Howler actual NPC
  coordinates, rather than separately sampling each NPC in the sound subsystem.
- Source-art identity, character animation, mobile 100dvh and safety rules from
  `animated-world-guard` and `png-multiview-meta-game-fusion` remain mandatory.

## Authority and rights

Rapier is the **only** physics authority. Recast is the **only** route planner.
YUKA issues *NPC-only* steering directions; ECS never applies forces or teleports.
Story is still exclusively validated Rete/Ink graph data. ECS only transmits
bounded, typed events from those systems. Imported GLBs remain subject to
ScanCode / SHA-256 / glTF-Validator / meshopt / KTX2 preflight, unaffected by ECS.

## Run

```
python skills/meta-game-fusion/scripts/fusion_builder.py build --library /path/to/readonly-library --concept 'Ночной город' --out /tmp/mgf-city
python skills/meta-game-fusion/scripts/ecs_bridge.py audit --project /tmp/mgf-city
cd /tmp/mgf-city && npm install && npm run dev
```

The game runs only after npm dependencies are installed and a real browser
opens it; source creation is not evidence of visual performance. For a real
browser test use Playwright in both portrait and landscape modes. When npm
network access is missing, report this limitation and do not claim a PASS.
